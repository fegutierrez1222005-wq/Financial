"""Evaluation engine entry point.

``EvaluationEngine.evaluate`` takes a completed run and returns a full report: claim-level
verdicts, dimension scores, an overall score, and every failure with an explanation of why
it failed. It is pure — no database, no HTTP — so the same code path runs in the API, the
worker and the test suite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from finagent_core.errors import EvaluationFailedError
from finagent_core.logging import get_logger, log_context
from finagent_core.models.base import ModelProvider
from finagent_core.schemas.enums import RunStatus
from finagent_core.schemas.research import RunResult
from finagent_evaluation.cases import EvaluationCase, EvaluationSuite
from finagent_evaluation.claims import ExtractedClaim, claim_statistics, extract_claims
from finagent_evaluation.evaluators import default_evaluators
from finagent_evaluation.evaluators.base import (
    EvaluationBudget,
    EvaluationContext,
    Evaluator,
    EvaluatorOutcome,
    Failure,
)
from finagent_evaluation.scoring import Scorer, ScoreResult, collect_failures, collect_warnings
from finagent_evaluation.verification import ClaimVerdict, VerificationReport, verify_claims

logger = get_logger(__name__)


@dataclass
class EvaluationReport:
    run_id: str
    score: ScoreResult
    verification: VerificationReport
    claims: list[ExtractedClaim]
    failures: list[Failure]
    warnings: list[str]
    case_key: str | None = None
    case_passed: bool | None = None
    suite_key: str | None = None
    evaluators_run: list[str] = field(default_factory=list)
    judge_detail: dict[str, Any] = field(default_factory=dict)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def overall(self) -> float:
        return self.score.overall

    def verdicts(self) -> list[ClaimVerdict]:
        return self.verification.verdicts

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "suite_key": self.suite_key,
            "case_key": self.case_key,
            "case_passed": self.case_passed,
            "overall_score": round(self.overall, 2),
            "score": self.score.as_dict(),
            "verification": self.verification.as_dict(),
            "claim_statistics": claim_statistics(self.claims),
            "claims": [
                {
                    "text": verdict.claim.text,
                    "kind": verdict.claim.kind.value,
                    "section": verdict.claim.section,
                    "support_level": verdict.support_level.value,
                    "cited_chunk_ids": verdict.claim.cited_chunk_ids,
                    "matched_chunk_id": verdict.matched_chunk_id,
                    "evidence_quote": verdict.evidence_quote,
                    "similarity": verdict.similarity,
                    "explanation": verdict.explanation,
                    "numbers_checked": verdict.numbers_checked,
                    "numbers_matched": verdict.numbers_matched,
                }
                for verdict in self.verification.verdicts
            ],
            "failures": [failure.as_dict() for failure in self.failures],
            "warnings": self.warnings,
            "evaluators_run": self.evaluators_run,
            "judge": self.judge_detail,
            "evaluated_at": self.evaluated_at.isoformat(),
            "detail": self.detail,
        }


class EvaluationEngine:
    def __init__(self, evaluators: list[Evaluator] | None = None) -> None:
        self.evaluators = evaluators or default_evaluators()

    def evaluate(
        self,
        run: RunResult,
        *,
        case: EvaluationCase | None = None,
        suite: EvaluationSuite | None = None,
        repeat_runs: list[RunResult] | None = None,
        judge_provider: ModelProvider | None = None,
        judge_model: str | None = None,
        budget: EvaluationBudget | None = None,
        weights: dict[str, float] | None = None,
        evaluation_id: str | None = None,
    ) -> EvaluationReport:
        if run.status in (RunStatus.QUEUED, RunStatus.RUNNING):
            raise EvaluationFailedError(
                "cannot evaluate a run that has not finished", details={"status": run.status}
            )

        with log_context(run_id=run.run_id, evaluation_id=evaluation_id):
            claims = extract_claims(run)
            verification = verify_claims(
                claims,
                run.evidence,
                cutoff_iso=run.information_cutoff.isoformat() if run.information_cutoff else None,
            )

            context = EvaluationContext(
                run=run,
                claims=claims,
                verification=verification,
                case=case,
                repeat_runs=repeat_runs or [],
                budget=budget or EvaluationBudget(),
                judge_provider=judge_provider,
                judge_model=judge_model,
            )

            outcomes: list[EvaluatorOutcome] = []
            ran: list[str] = []
            judge_detail: dict[str, Any] = {}
            case_passed: bool | None = None

            for evaluator in self.evaluators:
                if not evaluator.applicable(context):
                    continue
                try:
                    outcome = evaluator.evaluate(context)
                except Exception as exc:  # one bad evaluator must not void the evaluation
                    logger.exception(
                        "evaluator_failed", extra={"evaluator": evaluator.key, "run_id": run.run_id}
                    )
                    outcomes.append(
                        EvaluatorOutcome(
                            warnings=[
                                (
                                    f"Evaluator '{evaluator.key}' failed and was skipped "
                                    f"({type(exc).__name__})."
                                )
                            ]
                        )
                    )
                    continue
                outcomes.append(outcome)
                ran.append(evaluator.key)
                if evaluator.key == "llm_judge":
                    judge_detail = outcome.detail
                if outcome.passed is not None:
                    case_passed = (
                        outcome.passed if case_passed is None else (case_passed and outcome.passed)
                    )

            effective_weights = dict(suite.weights) if suite and suite.weights else {}
            effective_weights.update(weights or {})
            score = Scorer(effective_weights or None).score(outcomes)

            failures = collect_failures(outcomes)
            warnings = collect_warnings(outcomes)
            if run.status == RunStatus.FAILED:
                warnings.insert(
                    0, f"The run itself failed ({run.error_code}); scores reflect a partial run."
                )
            if run.used_mock_model:
                warnings.append(
                    "This run used the deterministic mock provider. Scores measure the platform "
                    "pipeline, not a language model's ability."
                )

            report = EvaluationReport(
                run_id=run.run_id,
                score=score,
                verification=verification,
                claims=claims,
                failures=failures,
                warnings=warnings,
                case_key=case.key if case else None,
                case_passed=case_passed,
                suite_key=suite.key if suite else None,
                evaluators_run=ran,
                judge_detail=judge_detail,
                detail={
                    "run_status": run.status,
                    "used_mock_model": run.used_mock_model,
                    "evidence_count": len(run.evidence),
                    "tool_calls": len(run.tool_calls),
                    "reproducibility_key": run.spec.reproducibility_key() if run.spec else None,
                },
            )
            logger.info(
                "evaluation_completed",
                extra={
                    "run_id": run.run_id,
                    "overall": report.overall,
                    "failures": len(failures),
                    "hallucination_rate": round(verification.hallucination_rate, 4),
                    "citation_coverage": round(verification.citation_coverage, 4),
                },
            )
            return report

    def evaluate_suite(
        self, suite: EvaluationSuite, runs_by_case: dict[str, RunResult], **kwargs: Any
    ) -> dict[str, EvaluationReport]:
        """Evaluate one run per case."""
        return {
            case.key: self.evaluate(runs_by_case[case.key], case=case, suite=suite, **kwargs)
            for case in suite.cases
            if case.key in runs_by_case
        }


def aggregate_suite_reports(reports: dict[str, EvaluationReport]) -> dict[str, Any]:
    """Suite-level roll-up: mean score, pass rate and per-dimension means."""
    if not reports:
        return {
            "case_count": 0,
            "passed": 0,
            "pass_rate": 0.0,
            "mean_overall": 0.0,
            "dimension_means": {},
            "failed_cases": [],
        }
    passed = sum(1 for report in reports.values() if report.case_passed)
    dimension_totals: dict[str, list[float]] = {}
    for report in reports.values():
        for dimension, value in report.score.dimension_scores().items():
            dimension_totals.setdefault(dimension, []).append(value)
    return {
        "case_count": len(reports),
        "passed": passed,
        "pass_rate": round(passed / len(reports) * 100.0, 2),
        "mean_overall": round(sum(report.overall for report in reports.values()) / len(reports), 2),
        "dimension_means": {
            dimension: round(sum(values) / len(values), 2)
            for dimension, values in sorted(dimension_totals.items())
        },
        "failed_cases": [
            {
                "case_key": key,
                "overall": round(report.overall, 2),
                "failures": [failure.as_dict() for failure in report.failures[:5]],
            }
            for key, report in reports.items()
            if report.case_passed is False
        ],
        "mean_hallucination_rate": round(
            sum(report.verification.hallucination_rate for report in reports.values()) / len(reports), 4
        ),
        "mean_citation_coverage": round(
            sum(report.verification.citation_coverage for report in reports.values()) / len(reports), 4
        ),
    }
