"""Evaluation orchestration and persistence.

Two entry points: :func:`evaluate_run` scores one completed research run;
:func:`run_suite` executes every case in a golden suite with one agent version and
aggregates — that is what produces a benchmark-grade number.

Persisted artefacts: dimension scores, per-case results with failure explanations, extracted
claims with their support verdicts, and citations linking claims to chunks.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from finagent_api.db.models import (
    Agent,
    AgentVersion,
    Citation,
    Claim,
    Evaluation,
    EvaluationResult,
    EvaluationScore,
    ResearchRun,
    ResearchTask,
)
from finagent_api.db.models import EvaluationCase as EvaluationCaseRow
from finagent_api.db.models import EvaluationSuite as EvaluationSuiteRow
from finagent_api.services import agent_service, research_service
from finagent_api.services.audit import AuditAction, record_audit
from finagent_api.services.providers import judge_provider
from finagent_api.services.research_service import TaskDraft
from finagent_api.services.usage_service import enforce_quota, record_usage
from finagent_core.errors import NotFoundError, ValidationFailedError
from finagent_core.logging import get_logger, log_context
from finagent_core.schemas.enums import RunStatus, UsageKind
from finagent_evaluation import (
    BUILTIN_SUITES,
    EvaluationEngine,
    EvaluationReport,
    aggregate_suite_reports,
)
from finagent_evaluation.cases import EvaluationCase, EvaluationSuite

logger = get_logger(__name__)

_engine = EvaluationEngine()


def _suite_from_rows(db: DbSession, suite_row: EvaluationSuiteRow) -> EvaluationSuite:
    cases = list(
        db.scalars(
            select(EvaluationCaseRow)
            .where(EvaluationCaseRow.suite_id == suite_row.id)
            .order_by(EvaluationCaseRow.key)
        )
    )
    return EvaluationSuite(
        key=suite_row.key,
        version=suite_row.version,
        name=suite_row.name,
        description=suite_row.description or "",
        weights=suite_row.weights or {},
        is_builtin=suite_row.is_builtin,
        dataset_note=suite_row.dataset_note,
        cases=[
            EvaluationCase(
                key=case.key,
                question=case.question,
                expected_answer=case.expected_answer,
                expected_value=case.expected_value,
                unit=case.unit,
                acceptable_low=case.acceptable_low,
                acceptable_high=case.acceptable_high,
                required_sources=list(case.required_sources or []),
                forbidden_sources=list(case.forbidden_sources or []),
                required_fields=list(case.required_fields or []),
                difficulty=case.difficulty,
                category=case.category,
                evaluation_method=case.evaluation_method,
                information_cutoff=(
                    case.information_cutoff.date().isoformat() if case.information_cutoff else None
                ),
                inputs=case.inputs or {},
                notes=case.notes,
            )
            for case in cases
        ],
    )


def resolve_suite(db: DbSession, *, workspace_id: str, suite_key: str) -> EvaluationSuite:
    """Prefer the workspace's stored suite; fall back to the built-in definition."""
    row = db.scalar(
        select(EvaluationSuiteRow).where(
            EvaluationSuiteRow.workspace_id == workspace_id,
            EvaluationSuiteRow.key == suite_key,
            EvaluationSuiteRow.deleted_at.is_(None),
        )
    )
    if row is not None:
        suite = _suite_from_rows(db, row)
        if suite.cases:
            return suite
    builtin = BUILTIN_SUITES.get(suite_key)
    if builtin is None:
        raise NotFoundError(f"evaluation suite not found: {suite_key}")
    return builtin


def install_builtin_suites(
    db: DbSession, *, organization_id: str, workspace_id: str
) -> list[EvaluationSuiteRow]:
    """Materialise built-in suites into a workspace so cases can be edited and extended."""
    installed: list[EvaluationSuiteRow] = []
    for suite in BUILTIN_SUITES.values():
        existing = db.scalar(
            select(EvaluationSuiteRow).where(
                EvaluationSuiteRow.workspace_id == workspace_id, EvaluationSuiteRow.key == suite.key
            )
        )
        if existing is not None:
            installed.append(existing)
            continue
        row = EvaluationSuiteRow(
            organization_id=organization_id,
            workspace_id=workspace_id,
            key=suite.key,
            version=suite.version,
            name=suite.name,
            description=suite.description,
            weights=suite.weights,
            is_builtin=True,
            dataset_note=suite.dataset_note,
        )
        db.add(row)
        db.flush()
        for case in suite.cases:
            db.add(
                EvaluationCaseRow(
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                    suite_id=row.id,
                    key=case.key,
                    question=case.question,
                    expected_answer=case.expected_answer,
                    expected_value=case.expected_value,
                    unit=case.unit,
                    acceptable_low=case.acceptable_low,
                    acceptable_high=case.acceptable_high,
                    required_sources=case.required_sources,
                    forbidden_sources=case.forbidden_sources,
                    required_fields=case.required_fields,
                    difficulty=case.difficulty,
                    category=case.category,
                    evaluation_method=case.evaluation_method,
                    information_cutoff=(
                        datetime.fromisoformat(case.information_cutoff).replace(tzinfo=timezone.utc)
                        if case.information_cutoff
                        else None
                    ),
                    inputs=case.inputs,
                    notes=case.notes,
                )
            )
        db.flush()
        installed.append(row)
    return installed


def create_evaluation(
    db: DbSession,
    *,
    organization_id: str,
    workspace_id: str,
    kind: str,
    run_id: str | None = None,
    suite_key: str | None = None,
    agent_id: str | None = None,
    agent_version_id: str | None = None,
    experiment_run_id: str | None = None,
    weights: dict[str, float] | None = None,
    user_id: str | None = None,
) -> Evaluation:
    enforce_quota(db, organization_id=organization_id, kind=UsageKind.EVALUATION_RUN)
    evaluation = Evaluation(
        organization_id=organization_id,
        workspace_id=workspace_id,
        kind=kind,
        run_id=run_id,
        suite_key=suite_key,
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        experiment_run_id=experiment_run_id,
        status=RunStatus.QUEUED.value,
        weights=weights or {},
        triggered_by_user_id=user_id,
    )
    db.add(evaluation)
    db.flush()
    record_audit(
        db,
        action=AuditAction.EVALUATION_STARTED,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        resource_type="evaluation",
        resource_id=evaluation.id,
        metadata={"kind": kind, "run_id": run_id, "suite_key": suite_key},
    )
    return evaluation


def evaluate_run(db: DbSession, *, evaluation_id: str) -> Evaluation:
    """Score a single research run and persist the report."""
    evaluation = db.get(Evaluation, evaluation_id)
    if evaluation is None:
        raise NotFoundError("evaluation not found")
    if evaluation.run_id is None:
        raise ValidationFailedError("this evaluation has no run to score")

    run = db.get(ResearchRun, evaluation.run_id)
    if run is None:
        raise NotFoundError("research run not found")

    evaluation.status = RunStatus.RUNNING.value
    evaluation.started_at = datetime.now(timezone.utc)
    db.flush()
    started = time.perf_counter()

    with log_context(evaluation_id=evaluation.id, run_id=run.id):
        result = research_service.load_run_result(db, run)
        suite = case = None
        task = db.get(ResearchTask, run.task_id) if run.task_id else None
        if task and task.evaluation_suite_key:
            suite = resolve_suite(db, workspace_id=run.workspace_id, suite_key=task.evaluation_suite_key)
            if task.evaluation_case_key:
                case = suite.case(task.evaluation_case_key)
        elif evaluation.suite_key:
            suite = resolve_suite(db, workspace_id=run.workspace_id, suite_key=evaluation.suite_key)

        provider, judge_model = judge_provider()
        report = _engine.evaluate(
            result,
            case=case,
            suite=suite,
            judge_provider=provider,
            judge_model=judge_model,
            weights=evaluation.weights or None,
            evaluation_id=evaluation.id,
        )
        _persist_report(
            db,
            evaluation=evaluation,
            run=run,
            report=report,
            judge_model=judge_model,
            judge_is_mock=bool(provider and provider.is_mock),
        )

    evaluation.duration_ms = int((time.perf_counter() - started) * 1000)
    evaluation.status = RunStatus.SUCCEEDED.value
    evaluation.finished_at = datetime.now(timezone.utc)
    db.flush()

    record_usage(
        db,
        organization_id=evaluation.organization_id,
        workspace_id=evaluation.workspace_id,
        user_id=evaluation.triggered_by_user_id,
        kind=UsageKind.EVALUATION_RUN,
        evaluation_id=evaluation.id,
        run_id=run.id,
        detail={"overall_score": evaluation.overall_score},
    )
    record_audit(
        db,
        action=AuditAction.EVALUATION_COMPLETED,
        organization_id=evaluation.organization_id,
        workspace_id=evaluation.workspace_id,
        user_id=evaluation.triggered_by_user_id,
        resource_type="evaluation",
        resource_id=evaluation.id,
        metadata={
            "overall_score": evaluation.overall_score,
            "hallucination_rate": evaluation.hallucination_rate,
            "citation_coverage": evaluation.citation_coverage,
        },
    )
    return evaluation


def _persist_report(
    db: DbSession,
    *,
    evaluation: Evaluation,
    run: ResearchRun,
    report: EvaluationReport,
    judge_model: str | None,
    judge_is_mock: bool,
) -> None:
    evaluation.overall_score = report.overall
    evaluation.hallucination_rate = report.verification.hallucination_rate
    evaluation.citation_coverage = report.verification.citation_coverage
    evaluation.judge_model = judge_model
    evaluation.judge_is_mock = judge_is_mock
    evaluation.warnings = report.warnings
    evaluation.case_count = 1 if report.case_key else 0
    evaluation.passed_count = 1 if report.case_passed else 0
    evaluation.summary = {
        "score": report.score.as_dict(),
        "verification": report.verification.as_dict(),
        "claim_statistics": report.as_dict()["claim_statistics"],
        "evaluators_run": report.evaluators_run,
        "judge": report.judge_detail,
        "case_key": report.case_key,
        "case_passed": report.case_passed,
    }

    # Propagate headline metrics onto the run for list views.
    run.citation_coverage = report.verification.citation_coverage
    run.hallucination_rate = report.verification.hallucination_rate

    db.query(EvaluationScore).filter(EvaluationScore.evaluation_id == evaluation.id).delete()
    for dimension in report.score.dimensions:
        db.add(
            EvaluationScore(
                organization_id=evaluation.organization_id,
                workspace_id=evaluation.workspace_id,
                evaluation_id=evaluation.id,
                dimension=dimension.dimension.value,
                score=dimension.score,
                weight=dimension.weight,
                detail={"contributions": [item.as_dict() for item in dimension.contributions]},
            )
        )

    for failure in report.failures:
        db.add(
            EvaluationResult(
                organization_id=evaluation.organization_id,
                workspace_id=evaluation.workspace_id,
                evaluation_id=evaluation.id,
                case_key=report.case_key,
                run_id=run.id,
                passed=False,
                expected=failure.expected,
                actual=failure.actual,
                failure_code=failure.code,
                failure_title=failure.title,
                failure_reason=failure.message,
                severity=failure.severity.value,
                dimension=failure.dimension.value if failure.dimension else None,
                evaluator=failure.evaluator,
                source=failure.source,
            )
        )
    if report.case_key is not None:
        db.add(
            EvaluationResult(
                organization_id=evaluation.organization_id,
                workspace_id=evaluation.workspace_id,
                evaluation_id=evaluation.id,
                case_key=report.case_key,
                run_id=run.id,
                passed=bool(report.case_passed),
                score=report.overall,
                detail={"summary": "case outcome"},
            )
        )

    db.query(Claim).filter(Claim.run_id == run.id, Claim.evaluation_id == evaluation.id).delete()
    db.query(Citation).filter(Citation.run_id == run.id).delete()
    for index, verdict in enumerate(report.verification.verdicts):
        numeric = verdict.claim.numbers[0] if verdict.claim.numbers else None
        db.add(
            Claim(
                organization_id=evaluation.organization_id,
                workspace_id=evaluation.workspace_id,
                run_id=run.id,
                evaluation_id=evaluation.id,
                order_index=index,
                text=verdict.claim.text,
                kind=verdict.claim.kind.value,
                section=verdict.claim.section,
                numeric_value=numeric.value if numeric else None,
                unit=numeric.unit.value if numeric else None,
                support_level=verdict.support_level.value,
                cited_chunk_refs=verdict.claim.cited_chunk_ids,
                matched_chunk_ref=verdict.matched_chunk_id,
                evidence_quote=verdict.evidence_quote,
                similarity=verdict.similarity,
                explanation=verdict.explanation,
            )
        )
        if verdict.matched_chunk_id:
            db.add(
                Citation(
                    organization_id=evaluation.organization_id,
                    workspace_id=evaluation.workspace_id,
                    run_id=run.id,
                    claim_text=verdict.claim.text,
                    external_chunk_ref=verdict.matched_chunk_id,
                    quote=verdict.evidence_quote,
                    support_level=verdict.support_level.value,
                    similarity=verdict.similarity,
                )
            )
    db.flush()


def run_suite(
    db: DbSession,
    *,
    organization_id: str,
    workspace_id: str,
    suite_key: str,
    agent_id: str,
    agent_version_id: str | None = None,
    model_override: str | None = None,
    user_id: str | None = None,
    experiment_run_id: str | None = None,
    max_cases: int | None = None,
    evaluation_id: str | None = None,
) -> Evaluation:
    """Run every case in a suite against one agent version and aggregate the results.

    ``evaluation_id`` lets the caller create the row first and hand the execution to a
    worker, so the client always has an id to poll regardless of the queue backend.
    """
    suite = resolve_suite(db, workspace_id=workspace_id, suite_key=suite_key)
    agent = agent_service.get_agent(db, workspace_id=workspace_id, agent_id=agent_id)
    version = (
        agent_service.get_version(db, workspace_id=workspace_id, version_id=agent_version_id)
        if agent_version_id
        else agent_service.current_version(db, agent)
    )

    if evaluation_id:
        evaluation = get_evaluation(db, workspace_id=workspace_id, evaluation_id=evaluation_id)
        evaluation.suite_key = suite.key
        evaluation.agent_id = agent.id
        evaluation.agent_version_id = version.id
        evaluation.weights = evaluation.weights or suite.weights
    else:
        evaluation = create_evaluation(
            db,
            organization_id=organization_id,
            workspace_id=workspace_id,
            kind="suite",
            suite_key=suite.key,
            agent_id=agent.id,
            agent_version_id=version.id,
            experiment_run_id=experiment_run_id,
            weights=suite.weights,
            user_id=user_id,
        )
    evaluation.status = RunStatus.RUNNING.value
    evaluation.started_at = datetime.now(timezone.utc)
    db.flush()

    started = time.perf_counter()
    provider, judge_model = judge_provider()
    cases = suite.cases[:max_cases] if max_cases else suite.cases
    reports: dict[str, EvaluationReport] = {}
    run_ids: dict[str, str] = {}

    for case in cases:
        cutoff = (
            datetime.fromisoformat(case.information_cutoff).replace(tzinfo=timezone.utc)
            if case.information_cutoff
            else None
        )
        task = research_service.create_task(
            db,
            organization_id=organization_id,
            workspace_id=workspace_id,
            user_id=user_id,
            draft=TaskDraft(
                template="custom",
                title=f"{suite.key}:{case.key}",
                question=case.question,
                inputs={**case.inputs, "question": case.question},
                information_cutoff=cutoff,
                evaluation_case_key=case.key,
                evaluation_suite_key=suite.key,
            ),
        )
        run = research_service.create_run(
            db,
            organization_id=organization_id,
            workspace_id=workspace_id,
            task=task,
            agent=agent,
            version=version,
            user_id=user_id,
            model_override=model_override,
            experiment_run_id=experiment_run_id,
        )
        try:
            research_service.execute_run(db, run.id)
        except Exception as exc:  # noqa: BLE001 - a failed case is a result, not a crash
            logger.warning(
                "suite_case_run_failed",
                extra={"case_key": case.key, "run_id": run.id, "error": type(exc).__name__},
            )
        db.refresh(run)
        run_ids[case.key] = run.id
        reports[case.key] = _engine.evaluate(
            research_service.load_run_result(db, run),
            case=case,
            suite=suite,
            judge_provider=provider,
            judge_model=judge_model,
            evaluation_id=evaluation.id,
        )

    aggregate = aggregate_suite_reports(reports)
    evaluation.status = RunStatus.SUCCEEDED.value
    evaluation.finished_at = datetime.now(timezone.utc)
    evaluation.duration_ms = int((time.perf_counter() - started) * 1000)
    evaluation.overall_score = aggregate["mean_overall"]
    evaluation.pass_rate = aggregate["pass_rate"]
    evaluation.case_count = aggregate["case_count"]
    evaluation.passed_count = aggregate["passed"]
    evaluation.hallucination_rate = aggregate.get("mean_hallucination_rate")
    evaluation.citation_coverage = aggregate.get("mean_citation_coverage")
    evaluation.judge_model = judge_model
    evaluation.judge_is_mock = bool(provider and provider.is_mock)
    evaluation.summary = {
        **aggregate,
        "suite_key": suite.key,
        "suite_version": suite.version,
        "agent_version_number": version.version_number,
        "model": model_override or version.model,
        "run_ids": run_ids,
        "dataset_note": suite.dataset_note,
    }
    evaluation.warnings = sorted({warning for report in reports.values() for warning in report.warnings})

    for dimension, value in aggregate["dimension_means"].items():
        db.add(
            EvaluationScore(
                organization_id=organization_id,
                workspace_id=workspace_id,
                evaluation_id=evaluation.id,
                dimension=dimension,
                score=value,
                weight=float(suite.weights.get(dimension, 0.0)),
                detail={"aggregate": "mean across cases"},
            )
        )

    for case_key, report in reports.items():
        suite_case = suite.case(case_key)
        db.add(
            EvaluationResult(
                organization_id=organization_id,
                workspace_id=workspace_id,
                evaluation_id=evaluation.id,
                case_key=case_key,
                run_id=run_ids.get(case_key),
                passed=bool(report.case_passed),
                score=report.overall,
                expected=suite_case.expected_answer if suite_case else None,
                actual=(report.failures[0].actual if report.failures else None),
                failure_code=report.failures[0].code if report.failures else None,
                failure_title=report.failures[0].title if report.failures else None,
                failure_reason=report.failures[0].message if report.failures else None,
                severity=(report.failures[0].severity.value if report.failures else "INFO"),
                evaluator=(report.failures[0].evaluator if report.failures else None),
                detail={
                    "dimension_scores": report.score.dimension_scores(),
                    "verification": report.verification.as_dict(),
                    "failures": [failure.as_dict() for failure in report.failures[:10]],
                },
            )
        )

    db.flush()
    record_usage(
        db,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        kind=UsageKind.EVALUATION_RUN,
        quantity=float(len(cases)),
        evaluation_id=evaluation.id,
        detail={"suite_key": suite.key, "pass_rate": evaluation.pass_rate},
    )
    record_audit(
        db,
        action=AuditAction.EVALUATION_COMPLETED,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        resource_type="evaluation",
        resource_id=evaluation.id,
        metadata={
            "suite_key": suite.key,
            "cases": len(cases),
            "pass_rate": evaluation.pass_rate,
            "mean_overall": evaluation.overall_score,
        },
    )
    logger.info(
        "suite_evaluation_completed",
        extra={
            "evaluation_id": evaluation.id,
            "suite_key": suite.key,
            "pass_rate": evaluation.pass_rate,
            "mean_overall": evaluation.overall_score,
        },
    )
    return evaluation


def get_evaluation(db: DbSession, *, workspace_id: str, evaluation_id: str) -> Evaluation:
    evaluation = db.get(Evaluation, evaluation_id)
    if evaluation is None or evaluation.workspace_id != workspace_id:
        raise NotFoundError("evaluation not found")
    return evaluation


def list_evaluations(
    db: DbSession,
    *,
    workspace_id: str,
    kind: str | None = None,
    agent_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Evaluation]:
    query = select(Evaluation).where(Evaluation.workspace_id == workspace_id)
    if kind:
        query = query.where(Evaluation.kind == kind)
    if agent_id:
        query = query.where(Evaluation.agent_id == agent_id)
    return list(
        db.scalars(query.order_by(Evaluation.created_at.desc()).limit(min(limit, 200)).offset(offset))
    )


def evaluation_detail(db: DbSession, evaluation: Evaluation) -> dict[str, Any]:
    scores = list(db.scalars(select(EvaluationScore).where(EvaluationScore.evaluation_id == evaluation.id)))
    results = list(
        db.scalars(
            select(EvaluationResult)
            .where(EvaluationResult.evaluation_id == evaluation.id)
            .order_by(EvaluationResult.severity)
        )
    )
    claims = (
        list(
            db.scalars(
                select(Claim).where(Claim.evaluation_id == evaluation.id).order_by(Claim.order_index)
            )
        )
        if evaluation.run_id
        else []
    )
    return {
        "scores": [
            {
                "dimension": score.dimension,
                "score": round(score.score, 2),
                "weight": round(score.weight, 4),
                "detail": score.detail,
            }
            for score in scores
        ],
        "results": [
            {
                "case_key": result.case_key,
                "run_id": result.run_id,
                "passed": result.passed,
                "score": result.score,
                "expected": result.expected,
                "actual": result.actual,
                "failure_code": result.failure_code,
                "failure_title": result.failure_title,
                "failure_reason": result.failure_reason,
                "severity": result.severity,
                "dimension": result.dimension,
                "evaluator": result.evaluator,
                "source": result.source,
                "detail": result.detail,
            }
            for result in results
        ],
        "claims": [
            {
                "text": claim.text,
                "kind": claim.kind,
                "section": claim.section,
                "support_level": claim.support_level,
                "cited_chunk_refs": claim.cited_chunk_refs,
                "matched_chunk_ref": claim.matched_chunk_ref,
                "evidence_quote": claim.evidence_quote,
                "similarity": claim.similarity,
                "explanation": claim.explanation,
            }
            for claim in claims
        ],
    }


def agent_scoreboard(
    db: DbSession, *, workspace_id: str, suite_key: str | None = None
) -> list[dict[str, Any]]:
    """Latest suite result per agent version — the data behind the leaderboard."""
    query = select(Evaluation).where(
        Evaluation.workspace_id == workspace_id,
        Evaluation.kind == "suite",
        Evaluation.status == RunStatus.SUCCEEDED.value,
    )
    if suite_key:
        query = query.where(Evaluation.suite_key == suite_key)

    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for evaluation in db.scalars(query.order_by(Evaluation.created_at.desc())):
        key = f"{evaluation.agent_version_id}:{evaluation.suite_key}"
        if key in seen or not evaluation.agent_id:
            continue
        seen.add(key)
        agent = db.get(Agent, evaluation.agent_id)
        version = (
            db.get(AgentVersion, evaluation.agent_version_id) if evaluation.agent_version_id else None
        )
        rows.append(
            {
                "evaluation_id": evaluation.id,
                "agent_id": evaluation.agent_id,
                "agent_name": agent.name if agent else None,
                "agent_version_id": evaluation.agent_version_id,
                "version_number": version.version_number if version else None,
                "model": (evaluation.summary or {}).get("model") or (version.model if version else None),
                "suite_key": evaluation.suite_key,
                "overall_score": evaluation.overall_score,
                "pass_rate": evaluation.pass_rate,
                "hallucination_rate": evaluation.hallucination_rate,
                "citation_coverage": evaluation.citation_coverage,
                "dimension_scores": {
                    score.dimension: round(score.score, 2)
                    for score in db.scalars(
                        select(EvaluationScore).where(EvaluationScore.evaluation_id == evaluation.id)
                    )
                },
                "judge_is_mock": evaluation.judge_is_mock,
                "evaluated_at": evaluation.finished_at.isoformat() if evaluation.finished_at else None,
            }
        )
    rows.sort(key=lambda row: row["overall_score"] or 0.0, reverse=True)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows
