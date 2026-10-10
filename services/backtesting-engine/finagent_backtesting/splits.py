"""Train / validation / out-of-sample evaluation and overfitting detection.

The out-of-sample window exists to be used **once**. Splits are reported separately and
never averaged, because an in-sample Sharpe of 2.1 next to an out-of-sample 0.8 *is* the
finding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from finagent_backtesting.dataset import PriceDataset
from finagent_backtesting.engine import BacktestResult, run_backtest
from finagent_backtesting.spec import BacktestSpec, SplitConfig
from finagent_backtesting.validation import Finding, FindingCode, Severity
from finagent_core.errors import ValidationFailedError
from finagent_core.schemas.enums import BacktestSplit


@dataclass
class OverfittingAssessment:
    """Platform-defined heuristic — not a statistical test."""

    train_sharpe: float
    validation_sharpe: float
    test_sharpe: float
    degradation_pct: float
    severity: str
    verdict: str
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "train_sharpe": round(self.train_sharpe, 3),
            "validation_sharpe": round(self.validation_sharpe, 3),
            "test_sharpe": round(self.test_sharpe, 3),
            "degradation_pct": round(self.degradation_pct, 2),
            "severity": self.severity,
            "verdict": self.verdict,
            "detail": self.detail,
            "method": "platform_heuristic",
        }


@dataclass
class SplitRunResult:
    results: dict[str, BacktestResult]
    overfitting: OverfittingAssessment | None

    @property
    def is_valid(self) -> bool:
        return all(result.is_valid for result in self.results.values())

    def summary(self) -> dict[str, Any]:
        return {
            "splits": {name: result.summary() for name, result in self.results.items()},
            "overfitting": self.overfitting.as_dict() if self.overfitting else None,
        }


def assess_overfitting(
    train: BacktestResult, validation: BacktestResult, test: BacktestResult
) -> OverfittingAssessment:
    train_sharpe = train.metrics.sharpe_ratio
    validation_sharpe = validation.metrics.sharpe_ratio
    test_sharpe = test.metrics.sharpe_ratio
    monotone_decay = train_sharpe > validation_sharpe > test_sharpe
    sign_flip = train_sharpe > 0 >= test_sharpe
    base_detail = {
        "monotone_decay": monotone_decay,
        "sign_flip": sign_flip,
        "train_cagr_pct": round(train.metrics.cagr_pct, 3),
        "validation_cagr_pct": round(validation.metrics.cagr_pct, 3),
        "test_cagr_pct": round(test.metrics.cagr_pct, 3),
        "train_max_drawdown_pct": round(train.metrics.max_drawdown_pct, 3),
        "test_max_drawdown_pct": round(test.metrics.max_drawdown_pct, 3),
    }

    if train_sharpe <= 0:
        # Decay is only meaningful relative to a profitable training window.
        return OverfittingAssessment(
            train_sharpe=train_sharpe,
            validation_sharpe=validation_sharpe,
            test_sharpe=test_sharpe,
            degradation_pct=0.0,
            severity="INFO",
            verdict=(
                "The training window was not profitable, so an overfitting comparison is not "
                "meaningful. Judge this strategy on the in-sample result first."
            ),
            detail={**base_detail, "not_applicable_reason": "train_sharpe_not_positive"},
        )

    degradation = (train_sharpe - test_sharpe) / abs(train_sharpe) * 100.0

    if sign_flip or degradation >= 60.0:
        severity = "CRITICAL"
        verdict = (
            "High overfitting risk: out-of-sample performance collapses relative to the training "
            "window. Treat the in-sample result as an artefact of fitting."
        )
    elif degradation >= 35.0 or monotone_decay:
        severity = "WARNING"
        verdict = (
            "Material performance decay across splits. The strategy may be fitted to the training "
            "window; re-test on a different period before relying on it."
        )
    elif degradation >= 15.0:
        severity = "INFO"
        verdict = "Mild decay across splits, within the range expected from sampling noise."
    else:
        severity = "INFO"
        verdict = "No material decay detected between in-sample and out-of-sample windows."

    return OverfittingAssessment(
        train_sharpe=train_sharpe,
        validation_sharpe=validation_sharpe,
        test_sharpe=test_sharpe,
        degradation_pct=degradation,
        severity=severity,
        verdict=verdict,
        detail=base_detail,
    )


def run_with_splits(
    spec: BacktestSpec, dataset: PriceDataset, *, test_split_use_count: int = 0
) -> SplitRunResult:
    """Run the full window plus each split, and assess overfitting."""
    if spec.split_config is None:
        raise ValidationFailedError("split_config is required for a split run")

    results: dict[str, BacktestResult] = {
        BacktestSplit.FULL.value: run_backtest(spec, dataset, split=BacktestSplit.FULL)
    }
    for split in (BacktestSplit.TRAIN, BacktestSplit.VALIDATION, BacktestSplit.TEST):
        results[split.value] = run_backtest(
            spec,
            dataset,
            split=split,
            test_split_use_count=test_split_use_count if split is BacktestSplit.TEST else 0,
        )

    assessment: OverfittingAssessment | None = None
    train = results[BacktestSplit.TRAIN.value]
    validation = results[BacktestSplit.VALIDATION.value]
    test = results[BacktestSplit.TEST.value]
    if train.is_valid and validation.is_valid and test.is_valid:
        assessment = assess_overfitting(train, validation, test)
        if assessment.severity in ("WARNING", "CRITICAL"):
            # Surfaced on the aggregate result so a reader cannot miss it.
            results[BacktestSplit.FULL.value].validation.add(
                Finding(
                    FindingCode.OVERFITTING_DEGRADATION,
                    Severity.WARNING if assessment.severity == "WARNING" else Severity.ERROR,
                    assessment.verdict,
                    {
                        "train_sharpe": round(assessment.train_sharpe, 3),
                        "validation_sharpe": round(assessment.validation_sharpe, 3),
                        "test_sharpe": round(assessment.test_sharpe, 3),
                        "degradation_pct": round(assessment.degradation_pct, 2),
                    },
                )
            )

    return SplitRunResult(results=results, overfitting=assessment)


def default_split_config() -> SplitConfig:
    return SplitConfig(train_pct=0.5, validation_pct=0.25, test_pct=0.25)
