"""Registered background jobs.

Every job opens its own database session. That is what makes the queue backend
interchangeable: the same function body is correct whether it is invoked inline by the API
process or by a Celery worker that shares nothing with the request. Callers must therefore
commit before submitting, and refresh afterwards.

Jobs never raise into the transport. They record the failure on the row they own (status,
``error_code``, ``error_message``) so the UI can explain what happened, and re-raise only
so the queue can log it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from finagent_api.db.session import session_scope
from finagent_api.jobs.queue import register_job
from finagent_core.errors import ErrorCode, FinagentError
from finagent_core.logging import get_logger, log_context
from finagent_core.schemas.enums import RunStatus

logger = get_logger(__name__)


def _record_failure(model, row_id: str, exc: Exception) -> None:
    """Mark a row failed in a fresh session after its own transaction rolled back.

    A job that raises loses everything it wrote, including the status it set to explain
    the failure. Without this the row would sit in ``QUEUED`` forever and the UI would
    show a run that is apparently still starting, hours later.
    """
    code = exc.code.value if isinstance(exc, FinagentError) else ErrorCode.INTERNAL_ERROR.value
    message = (
        exc.user_message
        if isinstance(exc, FinagentError)
        else "The job failed unexpectedly. The incident has been logged."
    )
    try:
        with session_scope() as db:
            row = db.get(model, row_id)
            if row is None:
                return
            row.status = RunStatus.FAILED.value
            row.error_code = code
            row.error_message = message
            if hasattr(row, "finished_at"):
                row.finished_at = datetime.now(UTC)
    except Exception:
        logger.exception("failure_record_failed", extra={"row_id": row_id})


@register_job("research.execute_run")
def execute_research_run(*, run_id: str) -> dict[str, Any]:
    from finagent_api.db.models import ResearchRun
    from finagent_api.services import research_service

    try:
        with log_context(run_id=run_id), session_scope() as db:
            run = research_service.execute_run(db, run_id)
            return {"run_id": run.id, "status": run.status}
    except Exception as exc:
        _record_failure(ResearchRun, run_id, exc)
        raise


@register_job("research.debate")
def run_debate(*, run_id: str, workspace_id: str) -> dict[str, Any]:
    from finagent_api.services import research_service

    with log_context(run_id=run_id), session_scope() as db:
        run = research_service.get_run(db, workspace_id=workspace_id, run_id=run_id)
        return research_service.run_debate(db, run=run)


@register_job("evaluation.evaluate_run")
def evaluate_run(*, evaluation_id: str) -> dict[str, Any]:
    from finagent_api.db.models import Evaluation
    from finagent_api.services import evaluation_service

    try:
        with log_context(evaluation_id=evaluation_id), session_scope() as db:
            evaluation = evaluation_service.evaluate_run(db, evaluation_id=evaluation_id)
            return {
                "evaluation_id": evaluation.id,
                "status": evaluation.status,
                "overall_score": evaluation.overall_score,
            }
    except Exception as exc:
        _record_failure(Evaluation, evaluation_id, exc)
        raise


@register_job("evaluation.run_suite")
def run_suite(
    *,
    organization_id: str,
    workspace_id: str,
    suite_key: str,
    agent_id: str,
    agent_version_id: str | None = None,
    model_override: str | None = None,
    user_id: str | None = None,
    max_cases: int | None = None,
    evaluation_id: str | None = None,
) -> dict[str, Any]:
    from finagent_api.db.models import Evaluation
    from finagent_api.services import evaluation_service

    try:
        with log_context(evaluation_id=evaluation_id), session_scope() as db:
            evaluation = evaluation_service.run_suite(
                db,
                organization_id=organization_id,
                workspace_id=workspace_id,
                suite_key=suite_key,
                agent_id=agent_id,
                agent_version_id=agent_version_id,
                model_override=model_override,
                user_id=user_id,
                max_cases=max_cases,
                evaluation_id=evaluation_id,
            )
            return {
                "evaluation_id": evaluation.id,
                "status": evaluation.status,
                "pass_rate": evaluation.pass_rate,
            }
    except Exception as exc:
        if evaluation_id:
            _record_failure(Evaluation, evaluation_id, exc)
        raise


@register_job("backtest.execute")
def execute_backtest(*, backtest_id: str, user_id: str | None = None) -> dict[str, Any]:
    from finagent_api.services import backtest_service

    # A backtest's status lives on its per-split runs, so there is no parent row to mark
    # failed; the error surfaces through the queue handle and the log.
    with log_context(backtest_id=backtest_id), session_scope() as db:
        runs = backtest_service.execute_backtest(db, backtest_id=backtest_id, user_id=user_id)
        return {
            "backtest_id": backtest_id,
            "runs": [{"split": run.split, "is_valid": run.is_valid, "status": run.status} for run in runs],
        }


@register_job("experiment.execute")
def execute_experiment(*, experiment_id: str, user_id: str | None = None) -> dict[str, Any]:
    from finagent_api.db.models import Experiment
    from finagent_api.services import experiment_service

    try:
        with log_context(experiment_id=experiment_id), session_scope() as db:
            experiment = experiment_service.execute_experiment(
                db, experiment_id=experiment_id, user_id=user_id
            )
            return {"experiment_id": experiment.id, "status": experiment.status}
    except Exception as exc:
        _record_failure(Experiment, experiment_id, exc)
        raise


@register_job("benchmark.execute")
def execute_benchmark(*, benchmark_id: str, user_id: str | None = None) -> dict[str, Any]:
    from finagent_api.db.models import Benchmark
    from finagent_api.services import experiment_service

    try:
        with log_context(benchmark_id=benchmark_id), session_scope() as db:
            benchmark = experiment_service.execute_benchmark(
                db, benchmark_id=benchmark_id, user_id=user_id
            )
            return {"benchmark_id": benchmark.id, "status": benchmark.status}
    except Exception as exc:
        _record_failure(Benchmark, benchmark_id, exc)
        raise


@register_job("webhook.deliver")
def deliver_webhook(*, delivery_id: str) -> dict[str, Any]:
    from finagent_api.services import notification_service

    with session_scope() as db:
        delivery = notification_service.attempt_delivery(db, delivery_id=delivery_id)
        return {"delivery_id": delivery.id, "status": delivery.status}


@register_job("webhook.retry_pending")
def retry_pending_webhooks(*, limit: int = 50) -> dict[str, Any]:
    """Periodic sweep for deliveries whose retry time has arrived."""
    from sqlalchemy import select

    from finagent_api.db.models import WebhookDelivery
    from finagent_api.services import notification_service

    now = datetime.now(UTC)
    attempted = 0
    with session_scope() as db:
        pending = db.scalars(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.status == "RETRYING",
                WebhookDelivery.next_attempt_at.is_not(None),
                WebhookDelivery.next_attempt_at <= now,
            )
            .limit(limit)
        )
        for delivery in list(pending):
            try:
                notification_service.attempt_delivery(db, delivery_id=delivery.id)
                attempted += 1
            except FinagentError as exc:
                logger.warning(
                    "webhook_retry_failed",
                    extra={"delivery_id": delivery.id, "error_code": exc.code.value},
                )
    return {"attempted": attempted}


@register_job("maintenance.expire_runs")
def expire_stuck_runs(*, older_than_seconds: int = 3600) -> dict[str, Any]:
    """Mark runs that never reported a terminal status as failed.

    A worker can be killed mid-run. Without this sweep the run would sit in ``RUNNING``
    forever and the dashboard would overstate activity.
    """
    from datetime import timedelta

    from sqlalchemy import select

    from finagent_api.db.models import ResearchRun

    threshold = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
    expired = 0
    with session_scope() as db:
        stuck = db.scalars(
            select(ResearchRun).where(
                ResearchRun.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value]),
                ResearchRun.created_at < threshold,
            )
        )
        for run in list(stuck):
            run.status = RunStatus.FAILED.value
            run.error_code = "AGENT_TIMEOUT"
            run.error_message = "The run did not report a result and was expired by maintenance."
            run.finished_at = datetime.now(UTC)
            expired += 1
    if expired:
        logger.warning("expired_stuck_runs", extra={"count": expired})
    return {"expired": expired}
