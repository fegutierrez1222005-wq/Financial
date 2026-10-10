"""Score composition.

The overall score is a configurable weighted average of dimension scores, where each
dimension's score is itself a weighted combination of the evaluators that scored it. Two
rules protect the number's meaning:

1. **Dimensions with no evidence are excluded** and the remaining weights renormalised. The
   platform does not invent a score for something it did not measure.
2. **LLM-judge scores are down-weighted**, so a persuasive answer cannot outscore a correct one.

The result is an *agent-quality* score. It says nothing about future investment returns and
is labelled as such wherever it appears.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from finagent_core.schemas.enums import EvaluationDimension

from finagent_evaluation.evaluators.base import (
    DimensionScore,
    EvaluatorKind,
    EvaluatorOutcome,
    Failure,
)

#: Default dimension weights. Suites and workspaces may override any subset.
DEFAULT_WEIGHTS: dict[EvaluationDimension, float] = {
    EvaluationDimension.FACTUAL_ACCURACY: 0.18,
    EvaluationDimension.CITATION_ACCURACY: 0.11,
    EvaluationDimension.CITATION_COMPLETENESS: 0.07,
    EvaluationDimension.NUMERICAL_ACCURACY: 0.13,
    EvaluationDimension.HALLUCINATION_RESISTANCE: 0.13,
    EvaluationDimension.FINANCIAL_REASONING: 0.09,
    EvaluationDimension.STATISTICAL_VALIDITY: 0.04,
    EvaluationDimension.INSTRUCTION_ADHERENCE: 0.05,
    EvaluationDimension.HISTORICAL_VALIDITY: 0.05,
    EvaluationDimension.ROBUSTNESS: 0.03,
    EvaluationDimension.REPRODUCIBILITY: 0.03,
    EvaluationDimension.OVERFITTING_RISK: 0.02,
    EvaluationDimension.TOOL_USE_EFFICIENCY: 0.02,
    EvaluationDimension.COST_EFFICIENCY: 0.02,
    EvaluationDimension.LATENCY: 0.01,
    EvaluationDimension.INVESTMENT_USEFULNESS: 0.02,
}

#: Relative trust in each evaluator kind when combining scores for one dimension.
KIND_WEIGHTS: dict[EvaluatorKind, float] = {
    EvaluatorKind.DETERMINISTIC: 1.0,
    EvaluatorKind.PROGRAMMATIC: 0.9,
    EvaluatorKind.LLM_JUDGE: 0.35,
}


@dataclass
class DimensionResult:
    dimension: EvaluationDimension
    score: float
    weight: float
    contributions: list[DimensionScore] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "score": round(self.score, 2),
            "weight": round(self.weight, 4),
            "contributions": [item.as_dict() for item in self.contributions],
        }


@dataclass
class ScoreResult:
    overall: float
    dimensions: list[DimensionResult]
    excluded_dimensions: list[str] = field(default_factory=list)
    weights_used: dict[str, float] = field(default_factory=dict)
    disclaimer: str = (
        "Agent-quality score (0-100). Measures research process quality — accuracy, evidence, "
        "reproducibility, cost. It does not predict investment returns."
    )

    def dimension_scores(self) -> dict[str, float]:
        return {item.dimension.value: round(item.score, 2) for item in self.dimensions}

    def as_dict(self) -> dict[str, Any]:
        return {
            "overall": round(self.overall, 2),
            "dimensions": [item.as_dict() for item in self.dimensions],
            "dimension_scores": self.dimension_scores(),
            "excluded_dimensions": self.excluded_dimensions,
            "weights_used": self.weights_used,
            "disclaimer": self.disclaimer,
        }


class Scorer:
    def __init__(self, weights: dict[str, float] | dict[EvaluationDimension, float] | None = None) -> None:
        self.weights: dict[EvaluationDimension, float] = dict(DEFAULT_WEIGHTS)
        for key, value in (weights or {}).items():
            dimension = EvaluationDimension(key) if isinstance(key, str) else key
            self.weights[dimension] = float(value)

    def score(self, outcomes: list[EvaluatorOutcome]) -> ScoreResult:
        grouped: dict[EvaluationDimension, list[DimensionScore]] = {}
        for outcome in outcomes:
            for item in outcome.scores:
                grouped.setdefault(item.dimension, []).append(item)

        present = [dimension for dimension in self.weights if dimension in grouped]
        excluded = [
            dimension.value
            for dimension in self.weights
            if dimension not in grouped and self.weights[dimension] > 0
        ]
        total_weight = sum(self.weights[dimension] for dimension in present)

        dimensions: list[DimensionResult] = []
        overall = 0.0
        for dimension in present:
            contributions = grouped[dimension]
            weight_sum = sum(KIND_WEIGHTS.get(item.kind, 0.5) for item in contributions)
            combined = (
                sum(item.score * KIND_WEIGHTS.get(item.kind, 0.5) for item in contributions) / weight_sum
                if weight_sum
                else 0.0
            )
            normalised_weight = self.weights[dimension] / total_weight if total_weight else 0.0
            overall += combined * normalised_weight
            dimensions.append(
                DimensionResult(
                    dimension=dimension,
                    score=combined,
                    weight=normalised_weight,
                    contributions=contributions,
                )
            )

        dimensions.sort(key=lambda item: item.weight, reverse=True)
        return ScoreResult(
            overall=round(overall, 2),
            dimensions=dimensions,
            excluded_dimensions=excluded,
            weights_used={item.dimension.value: round(item.weight, 4) for item in dimensions},
        )


def collect_failures(outcomes: list[EvaluatorOutcome]) -> list[Failure]:
    failures: list[Failure] = []
    for outcome in outcomes:
        failures.extend(outcome.failures)
    severity_rank = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    failures.sort(key=lambda failure: severity_rank.get(failure.severity.value, 3))
    return failures


def collect_warnings(outcomes: list[EvaluatorOutcome]) -> list[str]:
    warnings: list[str] = []
    for outcome in outcomes:
        for warning in outcome.warnings:
            if warning not in warnings:
                warnings.append(warning)
    return warnings
