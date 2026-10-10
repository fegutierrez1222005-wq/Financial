"""Evaluator interface.

Three evaluator kinds exist and they are *not* equal:

* ``deterministic`` — a fact either matches the expected value or it does not.
* ``programmatic`` — computed from run artefacts (numbers, timestamps, costs, trace).
* ``llm_judge`` — a model's opinion, deliberately down-weighted and never used alone.

Several evaluators may score the same dimension; the scorer combines them with the kind
weights, which is how the platform stops a fluent-but-wrong answer from scoring well.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from finagent_core.models.base import ModelProvider
from finagent_core.schemas.enums import EvaluationDimension
from finagent_core.schemas.research import RunResult

from finagent_evaluation.cases import EvaluationCase
from finagent_evaluation.claims import ExtractedClaim
from finagent_evaluation.verification import VerificationReport


class EvaluatorKind(StrEnum):
    DETERMINISTIC = "deterministic"
    PROGRAMMATIC = "programmatic"
    LLM_JUDGE = "llm_judge"


class FailureSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class EvaluationBudget:
    """Reference points for cost/latency scoring. Operator-configurable, not universal."""

    target_cost_usd: float = 0.25
    max_cost_usd: float = 2.00
    target_latency_ms: int = 30_000
    max_latency_ms: int = 180_000


@dataclass
class EvaluationContext:
    run: RunResult
    claims: list[ExtractedClaim]
    verification: VerificationReport
    case: EvaluationCase | None = None
    repeat_runs: list[RunResult] = field(default_factory=list)
    budget: EvaluationBudget = field(default_factory=EvaluationBudget)
    judge_provider: ModelProvider | None = None
    judge_model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def output_text(self) -> str:
        return self.run.output_text or ""

    def backtest_payloads(self) -> list[dict[str, Any]]:
        return [
            call.result
            for call in self.run.tool_calls
            if call.tool_name == "BACKTEST" and isinstance(call.result, dict)
        ]

    def calculator_payloads(self) -> list[dict[str, Any]]:
        return [
            call.result
            for call in self.run.tool_calls
            if call.tool_name == "CALCULATOR" and isinstance(call.result, dict)
        ]


@dataclass
class DimensionScore:
    dimension: EvaluationDimension
    score: float  # 0–100
    evaluator: str
    kind: EvaluatorKind
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "score": round(self.score, 2),
            "evaluator": self.evaluator,
            "kind": self.kind.value,
            "detail": self.detail,
        }


@dataclass
class Failure:
    code: str
    title: str
    message: str
    severity: FailureSeverity = FailureSeverity.WARNING
    expected: str | None = None
    actual: str | None = None
    source: str | None = None
    dimension: EvaluationDimension | None = None
    case_key: str | None = None
    evaluator: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "expected": self.expected,
            "actual": self.actual,
            "source": self.source,
            "dimension": self.dimension.value if self.dimension else None,
            "case_key": self.case_key,
            "evaluator": self.evaluator,
        }


@dataclass
class EvaluatorOutcome:
    scores: list[DimensionScore] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)
    #: Set by deterministic case evaluators so suite runs can report pass/fail per case.
    passed: bool | None = None


class Evaluator(abc.ABC):
    key: str = "abstract"
    kind: EvaluatorKind = EvaluatorKind.PROGRAMMATIC
    dimensions: tuple[EvaluationDimension, ...] = ()
    #: When True the evaluator is skipped unless a case is attached.
    requires_case: bool = False

    def applicable(self, context: EvaluationContext) -> bool:
        return not (self.requires_case and context.case is None)

    @abc.abstractmethod
    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome: ...

    def score_for(self, dimension: EvaluationDimension, score: float, **detail: Any) -> DimensionScore:
        return DimensionScore(
            dimension=dimension,
            score=max(0.0, min(100.0, float(score))),
            evaluator=self.key,
            kind=self.kind,
            detail=detail,
        )
