"""Backtest validation.

An unvalidated backtest is not reported as a result. Findings with ``ERROR`` severity make
the run invalid: the API refuses to present its metrics, and the UI shows why instead of a
Sharpe ratio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import pandas as pd

from finagent_backtesting.dataset import PriceDataset
from finagent_backtesting.spec import BacktestSpec
from finagent_core.schemas.enums import BacktestSplit


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class FindingCode(StrEnum):
    LOOK_AHEAD_SIGNAL_LAG = "LOOK_AHEAD_SIGNAL_LAG"
    LOOK_AHEAD_TRADE_TIMESTAMP = "LOOK_AHEAD_TRADE_TIMESTAMP"
    LOOK_AHEAD_CUTOFF = "LOOK_AHEAD_CUTOFF"
    LOOK_AHEAD_FACTOR_LAG = "LOOK_AHEAD_FACTOR_LAG"
    SURVIVORSHIP_STATIC_UNIVERSE = "SURVIVORSHIP_STATIC_UNIVERSE"
    SURVIVORSHIP_LATE_LISTING = "SURVIVORSHIP_LATE_LISTING"
    DATA_LEAKAGE_SPLIT_OVERLAP = "DATA_LEAKAGE_SPLIT_OVERLAP"
    DATA_LEAKAGE_TEST_REUSE = "DATA_LEAKAGE_TEST_REUSE"
    ZERO_TRANSACTION_COST = "ZERO_TRANSACTION_COST"
    ZERO_SLIPPAGE = "ZERO_SLIPPAGE"
    MISSING_DATA = "MISSING_DATA"
    SYMBOL_UNAVAILABLE = "SYMBOL_UNAVAILABLE"
    UNADJUSTED_PRICES = "UNADJUSTED_PRICES"
    SHORT_HISTORY = "SHORT_HISTORY"
    FEW_REBALANCES = "FEW_REBALANCES"
    DEMO_DATA = "DEMO_DATA"
    CONCENTRATION = "CONCENTRATION"
    OVERFITTING_DEGRADATION = "OVERFITTING_DEGRADATION"


@dataclass(frozen=True)
class Finding:
    code: FindingCode
    severity: Severity
    message: str
    detail: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
            "detail": self.detail,
        }


@dataclass
class ValidationReport:
    findings: list[Finding] = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    @property
    def errors(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.severity is Severity.WARNING]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def as_list(self) -> list[dict[str, object]]:
        return [finding.as_dict() for finding in self.findings]

    def codes(self) -> set[str]:
        return {finding.code.value for finding in self.findings}


def validate_pre_run(
    spec: BacktestSpec,
    dataset: PriceDataset,
    *,
    split: BacktestSplit = BacktestSplit.FULL,
    test_split_use_count: int = 0,
    missing_threshold: float = 0.05,
) -> ValidationReport:
    """Checks that can be made before simulating. Errors block execution."""
    report = ValidationReport()

    if spec.signal_lag_days < 1:
        report.add(
            Finding(
                FindingCode.LOOK_AHEAD_SIGNAL_LAG,
                Severity.ERROR,
                "Potential look-ahead bias: signals would be observed and traded on the same bar. "
                "Set signal_lag_days to at least 1.",
                {"signal_lag_days": spec.signal_lag_days},
            )
        )

    if spec.information_cutoff and spec.end_date > spec.information_cutoff:
        report.add(
            Finding(
                FindingCode.LOOK_AHEAD_CUTOFF,
                Severity.ERROR,
                "Backtest window extends past the information cutoff, which would trade on data "
                "the strategy could not have seen.",
                {
                    "end_date": spec.end_date.isoformat(),
                    "cutoff": spec.information_cutoff.isoformat(),
                },
            )
        )

    if dataset.prices.empty:
        report.add(
            Finding(
                FindingCode.MISSING_DATA,
                Severity.ERROR,
                "No price data was available for the requested universe and window.",
                {"universe": spec.universe},
            )
        )
        return report

    missing_symbols = [symbol for symbol in spec.universe if symbol not in dataset.prices.columns]
    if missing_symbols:
        report.add(
            Finding(
                FindingCode.SYMBOL_UNAVAILABLE,
                Severity.ERROR if len(missing_symbols) == len(spec.universe) else Severity.WARNING,
                f"No data for {len(missing_symbols)} of {len(spec.universe)} requested symbols; "
                "they were excluded from the simulation.",
                {"symbols": missing_symbols},
            )
        )

    if spec.transaction_cost_bps <= 0:
        report.add(
            Finding(
                FindingCode.ZERO_TRANSACTION_COST,
                Severity.WARNING,
                "Transaction costs are zero. Reported returns are not achievable net of "
                "commissions and fees.",
                {"transaction_cost_bps": spec.transaction_cost_bps},
            )
        )
    if spec.slippage_bps <= 0:
        report.add(
            Finding(
                FindingCode.ZERO_SLIPPAGE,
                Severity.WARNING,
                "Slippage is zero. Execution is assumed at the closing print with no market impact.",
                {"slippage_bps": spec.slippage_bps},
            )
        )

    rows = len(dataset.prices.index)
    for symbol, missing in dataset.missing_by_symbol.items():
        if rows and missing / rows > missing_threshold:
            report.add(
                Finding(
                    FindingCode.MISSING_DATA,
                    Severity.WARNING,
                    f"{symbol} is missing {missing} of {rows} observations "
                    f"({missing / rows:.1%}); gaps were forward filled for valuation only.",
                    {"symbol": symbol, "missing": missing, "rows": rows},
                )
            )

    if dataset.unadjusted_symbols:
        report.add(
            Finding(
                FindingCode.UNADJUSTED_PRICES,
                Severity.WARNING,
                "Some price series are not corporate-action adjusted. Splits and dividends will "
                "distort returns.",
                {"symbols": dataset.unadjusted_symbols},
            )
        )

    window_start = pd.Timestamp(spec.start_date)
    late_listings = {
        symbol: first.isoformat()
        for symbol, first in dataset.first_date_by_symbol.items()
        if pd.Timestamp(first) > window_start + pd.Timedelta(days=5)
    }
    if late_listings:
        report.add(
            Finding(
                FindingCode.SURVIVORSHIP_LATE_LISTING,
                Severity.WARNING,
                "Some symbols have no history at the start of the window; including them only "
                "after they appear biases results toward survivors.",
                {"symbols": late_listings},
            )
        )

    report.add(
        Finding(
            FindingCode.SURVIVORSHIP_STATIC_UNIVERSE,
            Severity.WARNING,
            "The universe is a fixed symbol list rather than point-in-time index membership, so "
            "delisted and acquired companies are absent. Treat results as survivorship biased.",
            {"universe_size": len(spec.universe)},
        )
    )

    if rows < 250:
        report.add(
            Finding(
                FindingCode.SHORT_HISTORY,
                Severity.WARNING,
                f"Only {rows} trading days in this window; risk statistics are unstable below "
                "roughly one year of data.",
                {"trading_days": rows},
            )
        )

    if spec.strategy.top_n <= 2:
        report.add(
            Finding(
                FindingCode.CONCENTRATION,
                Severity.WARNING,
                f"Holding only {spec.strategy.top_n} positions makes results highly sensitive to "
                "individual names.",
                {"top_n": spec.strategy.top_n},
            )
        )

    if dataset.is_demo:
        report.add(
            Finding(
                FindingCode.DEMO_DATA,
                Severity.WARNING,
                "This backtest ran on synthetic DEMO price data. Results describe the demo dataset "
                "only and carry no information about real markets.",
                {"sources": sorted(dataset.sources)},
            )
        )

    if spec.split_config is not None:
        windows = {
            item: spec.window_for(item)
            for item in (BacktestSplit.TRAIN, BacktestSplit.VALIDATION, BacktestSplit.TEST)
        }
        ordered = sorted(windows.items(), key=lambda item: item[1][0])
        for (left_name, left), (right_name, right) in zip(ordered, ordered[1:]):
            if left[1] >= right[0]:
                report.add(
                    Finding(
                        FindingCode.DATA_LEAKAGE_SPLIT_OVERLAP,
                        Severity.ERROR,
                        f"Data leakage: the {left_name.value} and {right_name.value} windows overlap.",
                        {
                            "left": [item.isoformat() for item in left],
                            "right": [item.isoformat() for item in right],
                        },
                    )
                )

    if split is BacktestSplit.TEST and test_split_use_count >= 1:
        report.add(
            Finding(
                FindingCode.DATA_LEAKAGE_TEST_REUSE,
                Severity.WARNING,
                f"The out-of-sample window has already been evaluated {test_split_use_count} "
                "time(s) for this configuration. Repeated use turns it into a validation set.",
                {"previous_uses": test_split_use_count},
            )
        )

    return report


def validate_execution(
    spec: BacktestSpec,
    *,
    signal_dates: list[pd.Timestamp],
    trade_dates: list[pd.Timestamp],
    rebalance_count: int,
) -> ValidationReport:
    """Post-simulation checks on what the engine actually did."""
    report = ValidationReport()

    for signal_date, trade_date in zip(signal_dates, trade_dates):
        if signal_date >= trade_date:
            report.add(
                Finding(
                    FindingCode.LOOK_AHEAD_TRADE_TIMESTAMP,
                    Severity.ERROR,
                    "Look-ahead bias detected: a signal timestamp is not strictly earlier than the "
                    "bar it traded on.",
                    {"signal_date": str(signal_date.date()), "trade_date": str(trade_date.date())},
                )
            )
            break

    if rebalance_count < 4:
        report.add(
            Finding(
                FindingCode.FEW_REBALANCES,
                Severity.WARNING,
                f"Only {rebalance_count} rebalance(s) occurred; the result is closer to a single "
                "bet than a strategy evaluation.",
                {"rebalances": rebalance_count},
            )
        )
    return report


def validate_factor_lag(dataset: PriceDataset, *, minimum_lag_days: int = 1) -> ValidationReport:
    """Ensure factor data is only used after its publication date."""
    report = ValidationReport()
    offenders = {
        symbol: lag
        for symbol, lag in dataset.factor_publication_lag_days.items()
        if lag < minimum_lag_days
    }
    if offenders:
        report.add(
            Finding(
                FindingCode.LOOK_AHEAD_FACTOR_LAG,
                Severity.ERROR,
                "Factor observations are dated on or before their period end, implying the data was "
                "used before it was published.",
                {"symbols": offenders},
            )
        )
    return report


def merge_reports(*reports: ValidationReport) -> ValidationReport:
    merged = ValidationReport()
    seen: set[tuple[str, str]] = set()
    for report in reports:
        for finding in report.findings:
            key = (finding.code.value, finding.message)
            if key in seen:
                continue
            seen.add(key)
            merged.add(finding)
    return merged
