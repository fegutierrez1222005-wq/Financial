"""Dashboard aggregation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from finagent_api.db.models import (
    Agent,
    Backtest,
    Document,
    Evaluation,
    EvaluationResult,
    EvaluationSuite,
    ResearchRun,
)
from finagent_api.services.usage_service import cost_trend, research_efficiency, usage_summary


def workspace_dashboard(
    db: DbSession, *, organization_id: str, workspace_id: str, days: int = 30
) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    agents = int(
        db.scalar(
            select(func.count(Agent.id)).where(
                Agent.workspace_id == workspace_id, Agent.deleted_at.is_(None)
            )
        )
        or 0
    )
    total_runs = int(
        db.scalar(select(func.count(ResearchRun.id)).where(ResearchRun.workspace_id == workspace_id)) or 0
    )
    runs_in_window, mean_duration, mean_cost, mean_citation, mean_hallucination = db.execute(
        select(
            func.count(ResearchRun.id),
            func.coalesce(func.avg(ResearchRun.duration_ms), 0.0),
            func.coalesce(func.avg(ResearchRun.estimated_cost_usd), 0.0),
            func.coalesce(func.avg(ResearchRun.citation_coverage), 0.0),
            func.coalesce(func.avg(ResearchRun.hallucination_rate), 0.0),
        ).where(ResearchRun.workspace_id == workspace_id, ResearchRun.created_at >= since)
    ).one()

    failed_runs = int(
        db.scalar(
            select(func.count(ResearchRun.id)).where(
                ResearchRun.workspace_id == workspace_id,
                ResearchRun.status == "FAILED",
                ResearchRun.created_at >= since,
            )
        )
        or 0
    )
    evaluations, mean_score, mean_pass_rate = db.execute(
        select(
            func.count(Evaluation.id),
            func.coalesce(func.avg(Evaluation.overall_score), 0.0),
            func.coalesce(func.avg(Evaluation.pass_rate), 0.0),
        ).where(Evaluation.workspace_id == workspace_id, Evaluation.created_at >= since)
    ).one()

    counts = {
        "suites": int(
            db.scalar(
                select(func.count(EvaluationSuite.id)).where(
                    EvaluationSuite.workspace_id == workspace_id,
                    EvaluationSuite.deleted_at.is_(None),
                )
            )
            or 0
        ),
        "documents": int(
            db.scalar(
                select(func.count(Document.id)).where(
                    Document.workspace_id == workspace_id, Document.deleted_at.is_(None)
                )
            )
            or 0
        ),
        "backtests": int(
            db.scalar(
                select(func.count(Backtest.id)).where(
                    Backtest.workspace_id == workspace_id, Backtest.deleted_at.is_(None)
                )
            )
            or 0
        ),
    }

    recent = list(
        db.scalars(
            select(ResearchRun)
            .where(ResearchRun.workspace_id == workspace_id)
            .order_by(ResearchRun.created_at.desc())
            .limit(10)
        )
    )
    failures = list(
        db.scalars(
            select(EvaluationResult)
            .where(
                EvaluationResult.workspace_id == workspace_id, EvaluationResult.severity == "CRITICAL"
            )
            .order_by(EvaluationResult.created_at.desc())
            .limit(10)
        )
    )

    agent_performance = []
    for agent_id, name, run_count, avg_cost, avg_duration in db.execute(
        select(
            Agent.id,
            Agent.name,
            func.count(ResearchRun.id),
            func.coalesce(func.avg(ResearchRun.estimated_cost_usd), 0.0),
            func.coalesce(func.avg(ResearchRun.duration_ms), 0.0),
        )
        .join(ResearchRun, ResearchRun.agent_id == Agent.id, isouter=True)
        .where(Agent.workspace_id == workspace_id, Agent.deleted_at.is_(None))
        .group_by(Agent.id, Agent.name)
    ):
        score = db.scalar(
            select(func.avg(Evaluation.overall_score)).where(
                Evaluation.workspace_id == workspace_id, Evaluation.agent_id == agent_id
            )
        )
        agent_performance.append(
            {
                "agent_id": agent_id,
                "agent_name": name,
                "runs": int(run_count or 0),
                "mean_score": round(float(score), 2) if score else None,
                "mean_cost_usd": round(float(avg_cost or 0.0), 6),
                "mean_duration_ms": int(avg_duration or 0),
            }
        )
    agent_performance.sort(key=lambda row: row["mean_score"] or -1, reverse=True)

    first_success = db.scalar(
        select(func.min(ResearchRun.finished_at)).where(
            ResearchRun.workspace_id == workspace_id, ResearchRun.status == "SUCCEEDED"
        )
    )
    first_run = db.scalar(
        select(func.min(ResearchRun.created_at)).where(ResearchRun.workspace_id == workspace_id)
    )
    total_evaluations = int(
        db.scalar(select(func.count(Evaluation.id)).where(Evaluation.workspace_id == workspace_id)) or 0
    )
    completed_evaluations = int(
        db.scalar(
            select(func.count(Evaluation.id)).where(
                Evaluation.workspace_id == workspace_id, Evaluation.status == "SUCCEEDED"
            )
        )
        or 0
    )

    return {
        "headline": {
            "total_agents": agents,
            "total_runs": total_runs,
            "runs_in_window": int(runs_in_window or 0),
            "failed_runs_in_window": failed_runs,
            "evaluations_in_window": int(evaluations or 0),
            "mean_evaluation_score": round(float(mean_score or 0.0), 2),
            "mean_pass_rate": round(float(mean_pass_rate or 0.0), 2),
            "mean_citation_coverage": round(float(mean_citation or 0.0) * 100.0, 2),
            "mean_hallucination_rate": round(float(mean_hallucination or 0.0) * 100.0, 2),
            "mean_cost_usd": round(float(mean_cost or 0.0), 6),
            "mean_duration_ms": int(mean_duration or 0),
            "evaluation_suites": counts["suites"],
            "documents": counts["documents"],
            "backtests": counts["backtests"],
        },
        "research_efficiency": research_efficiency(
            mean_score=float(mean_score or 0.0),
            mean_cost_usd=float(mean_cost or 0.0),
            mean_duration_ms=int(mean_duration or 0),
        ),
        "product_metrics": {
            "time_to_first_successful_run_seconds": (
                int((first_success - first_run).total_seconds()) if first_success and first_run else None
            ),
            "evaluation_completion_rate": round(
                completed_evaluations / max(total_evaluations, 1) * 100.0, 2
            ),
        },
        "recent_runs": [
            {
                "id": run.id,
                "status": run.status,
                "model": run.model,
                "agent_id": run.agent_id,
                "duration_ms": run.duration_ms,
                "estimated_cost_usd": run.estimated_cost_usd,
                "confidence": run.confidence,
                "citation_coverage": run.citation_coverage,
                "hallucination_rate": run.hallucination_rate,
                "used_mock_model": run.used_mock_model,
                "created_at": run.created_at.isoformat(),
                "error_code": run.error_code,
            }
            for run in recent
        ],
        "agent_performance": agent_performance,
        "evaluation_failures": [
            {
                "evaluation_id": failure.evaluation_id,
                "case_key": failure.case_key,
                "run_id": failure.run_id,
                "code": failure.failure_code,
                "title": failure.failure_title,
                "reason": failure.failure_reason,
                "expected": failure.expected,
                "actual": failure.actual,
                "dimension": failure.dimension,
                "created_at": failure.created_at.isoformat(),
            }
            for failure in failures
        ],
        "cost_trend": cost_trend(
            db, organization_id=organization_id, workspace_id=workspace_id, days=days
        ),
        "usage": usage_summary(
            db, organization_id=organization_id, workspace_id=workspace_id, days=days
        ),
    }


def admin_overview(db: DbSession, *, days: int = 30) -> dict[str, Any]:
    """Platform-wide view for administrators."""
    from finagent_api.db.models import (
        ApiKey,
        AuditLog,
        DataSource,
        ModelRun,
        Organization,
        RateLimitEvent,
        User,
        Workspace,
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)
    counts = {
        "users": int(db.scalar(select(func.count(User.id))) or 0),
        "organizations": int(db.scalar(select(func.count(Organization.id))) or 0),
        "workspaces": int(db.scalar(select(func.count(Workspace.id))) or 0),
        "agents": int(db.scalar(select(func.count(Agent.id))) or 0),
        "research_runs": int(db.scalar(select(func.count(ResearchRun.id))) or 0),
        "evaluations": int(db.scalar(select(func.count(Evaluation.id))) or 0),
        "documents": int(db.scalar(select(func.count(Document.id))) or 0),
        "api_keys": int(db.scalar(select(func.count(ApiKey.id)).where(ApiKey.revoked_at.is_(None))) or 0),
        "data_sources": int(db.scalar(select(func.count(DataSource.id))) or 0),
    }
    return {
        "counts": counts,
        "window_days": days,
        "model_usage": [
            {
                "model": model,
                "calls": int(calls or 0),
                "tokens": int(tokens or 0),
                "estimated_cost_usd": round(float(cost or 0.0), 6),
            }
            for model, calls, tokens, cost in db.execute(
                select(
                    ModelRun.model,
                    func.count(ModelRun.id),
                    func.coalesce(func.sum(ModelRun.input_tokens + ModelRun.output_tokens), 0),
                    func.coalesce(func.sum(ModelRun.estimated_cost_usd), 0.0),
                )
                .where(ModelRun.created_at >= since)
                .group_by(ModelRun.model)
            )
        ],
        "failed_runs": int(
            db.scalar(
                select(func.count(ResearchRun.id)).where(
                    ResearchRun.status == "FAILED", ResearchRun.created_at >= since
                )
            )
            or 0
        ),
        "security_events": [
            {
                "action": event.action,
                "user_id": event.user_id,
                "organization_id": event.organization_id,
                "outcome": event.outcome,
                "ip_address": event.ip_address,
                "created_at": event.created_at.isoformat(),
            }
            for event in db.scalars(
                select(AuditLog)
                .where(
                    AuditLog.created_at >= since,
                    AuditLog.action.in_(
                        [
                            "auth.login_failed",
                            "api_key.created",
                            "api_key.revoked",
                            "member.role_changed",
                            "permission.changed",
                        ]
                    ),
                )
                .order_by(AuditLog.created_at.desc())
                .limit(50)
            )
        ],
        "rate_limit_events": [
            {
                "scope": event.scope,
                "path": event.path,
                "limit": event.limit_value,
                "created_at": event.created_at.isoformat(),
            }
            for event in db.scalars(
                select(RateLimitEvent)
                .where(RateLimitEvent.created_at >= since)
                .order_by(RateLimitEvent.created_at.desc())
                .limit(50)
            )
        ],
    }
