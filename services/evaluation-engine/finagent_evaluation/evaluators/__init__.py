"""Evaluator registry."""

from finagent_evaluation.evaluators.base import (
    DimensionScore,
    EvaluationBudget,
    EvaluationContext,
    Evaluator,
    EvaluatorKind,
    EvaluatorOutcome,
    Failure,
    FailureSeverity,
)
from finagent_evaluation.evaluators.deterministic import (
    CitationDisciplineEvaluator,
    ExpectedValueEvaluator,
    RequiredFieldsEvaluator,
    SourceRequirementEvaluator,
)
from finagent_evaluation.evaluators.judge import LlmJudgeEvaluator
from finagent_evaluation.evaluators.programmatic import (
    CalculationCorrectnessEvaluator,
    CostLatencyEvaluator,
    HistoricalValidityEvaluator,
    NumericConsistencyEvaluator,
    OverfittingRiskEvaluator,
    ReasoningStructureEvaluator,
    ReproducibilityEvaluator,
    RobustnessEvaluator,
    StatisticalValidityEvaluator,
    ToolUseEfficiencyEvaluator,
)


def default_evaluators() -> list[Evaluator]:
    """Ordered so deterministic evidence is established before opinions are collected."""
    return [
        ExpectedValueEvaluator(),
        RequiredFieldsEvaluator(),
        SourceRequirementEvaluator(),
        CitationDisciplineEvaluator(),
        CalculationCorrectnessEvaluator(),
        NumericConsistencyEvaluator(),
        StatisticalValidityEvaluator(),
        HistoricalValidityEvaluator(),
        ToolUseEfficiencyEvaluator(),
        CostLatencyEvaluator(),
        ReproducibilityEvaluator(),
        RobustnessEvaluator(),
        OverfittingRiskEvaluator(),
        ReasoningStructureEvaluator(),
        LlmJudgeEvaluator(),
    ]


__all__ = [
    "DimensionScore",
    "EvaluationBudget",
    "EvaluationContext",
    "Evaluator",
    "EvaluatorKind",
    "EvaluatorOutcome",
    "Failure",
    "FailureSeverity",
    "CitationDisciplineEvaluator",
    "ExpectedValueEvaluator",
    "RequiredFieldsEvaluator",
    "SourceRequirementEvaluator",
    "LlmJudgeEvaluator",
    "CalculationCorrectnessEvaluator",
    "CostLatencyEvaluator",
    "HistoricalValidityEvaluator",
    "NumericConsistencyEvaluator",
    "OverfittingRiskEvaluator",
    "ReasoningStructureEvaluator",
    "ReproducibilityEvaluator",
    "RobustnessEvaluator",
    "StatisticalValidityEvaluator",
    "ToolUseEfficiencyEvaluator",
    "default_evaluators",
]
