"""Usage metering, quota enforcement and cost aggregation.

Cost figures are labelled estimates derived from the model catalog's rate card. The platform
reports cost per task, cost per *successful* task and cost per *accurate* answer, because
cost per token tells an institution nothing about value.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from finagent_api.db.models import Evaluation, ResearchRun, Subscription, UsageEvent
from finagent_core.errors import QuotaExceededError
from finagent_core.logging import get_logger
from finagent_core.schemas.enums import UsageKind

logger = get_logger(__name__)


def record_usage(
    db: DbSession,
    *,
    organization_id: str,
    kind: UsageKind | str,
    quantity: float = 1.0,
    unit: str = "count",
    cost_usd: float = 0.0,
    workspace_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
    evaluation_id: str | None = None,
    backtest_run_id: str | None = None,
    model: str | None = None,
    is_estimated: bool = True,
    detail: dict[str, Any] | None = None,
) -> UsageEvent:
    event = UsageEvent(
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        kind=str(kind),
        quantity=float(quantity),
        unit=unit,
        cost_usd=float(cost_usd),
        is_estimated=is_estimated,
        run_id=run_id,
        evaluation_id=evaluation_id,
        backtest_run_id=backtest_run_id,
        model=model,
        detail=detail or {},
    )
    db.add(event)
    db.flush()
    return event


def period_bounds(days: int = 30) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    return now - timedelta(days=days), now


def subscription_for(db: DbSession, organization_id: str) -> Subscription | None:
    return db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))


def count_usage(
    db: DbSession, *, organization_id: str, kind: UsageKind | str, since: datetime | None = None
) -> float:
    query = select(func.coalesce(func.sum(UsageEvent.quantity), 0.0)).where(
        UsageEvent.organization_id == organization_id, UsageEvent.kind == str(kind)
    )
    if since is not None:
        query = query.where(UsageEvent.created_at >= since)
    return float(db.scalar(query) or 0.0)


def enforce_quota(db: DbSession, *, organization_id: str, kind: UsageKind, requested: int = 1) -> None:
    """Raise :class:`QuotaExceededError` when the plan's allowance is exhausted."""
    subscription = subscription_for(db, organization_id)
    if subscription is None:
        return
    limit = {
        UsageKind.RESEARCH_RUN: subscription.research_run_limit,
        UsageKind.EVALUATION_RUN: subscription.evaluation_limit,
        UsageKind.BACKTEST_RUN: subscription.backtest_limit,
        UsageKind.DOCUMENT_PAGES: subscription.document_page_limit,
    }.get(kind)
    if not limit:
        return
    period_start = subscription.current_period_start or period_bounds()[0]
    used = count_usage(db, organization_id=organization_id, kind=kind, since=period_start)
    if used + requested > limit:
        raise QuotaExceededError(
            f"{kind.value} quota exhausted for the current period",
            details={"used": used, "limit": limit, "plan": subscription.plan},
        )

    if subscription.monthly_cost_cap_usd:
        spent = float(
            db.scalar(
                select(func.coalesce(func.sum(UsageEvent.cost_usd), 0.0)).where(
                    UsageEvent.organization_id == organization_id,
                    UsageEvent.created_at >= period_start,
                )
            )
            or 0.0
        )
        if spent >= subscription.monthly_cost_cap_usd:
            raise QuotaExceededError(
                "monthly estimated cost cap reached",
                details={"spent_usd": round(spent, 4), "cap_usd": subscription.monthly_cost_cap_usd},
            )


def usage_summary(
    db: DbSession, *, organization_id: str, workspace_id: str | None = None, days: int = 30
) -> dict[str, Any]:
    since, now = period_bounds(days)

    def scoped(query):
        query = query.where(
            UsageEvent.organization_id == organization_id, UsageEvent.created_at >= since
        )
        return query.where(UsageEvent.workspace_id == workspace_id) if workspace_id else query

    by_kind = {
        kind: {
            "quantity": float(quantity or 0.0),
            "cost_usd": round(float(cost or 0.0), 6),
            "events": int(count or 0),
        }
        for kind, quantity, cost, count in db.execute(
            scoped(
                select(
                    UsageEvent.kind,
                    func.sum(UsageEvent.quantity),
                    func.sum(UsageEvent.cost_usd),
                    func.count(UsageEvent.id),
                ).group_by(UsageEvent.kind)
            )
        )
    }
    by_model = [
        {"model": model, "quantity": float(quantity or 0.0), "cost_usd": round(float(cost or 0.0), 6)}
        for model, quantity, cost in db.execute(
            scoped(
                select(UsageEvent.model, func.sum(UsageEvent.quantity), func.sum(UsageEvent.cost_usd))
                .where(UsageEvent.model.is_not(None))
                .group_by(UsageEvent.model)
            )
        )
    ]

    run_query = select(
        func.count(ResearchRun.id),
        func.coalesce(func.sum(ResearchRun.estimated_cost_usd), 0.0),
        func.coalesce(func.avg(ResearchRun.duration_ms), 0.0),
        func.coalesce(func.sum(ResearchRun.input_tokens + ResearchRun.output_tokens), 0),
    ).where(ResearchRun.organization_id == organization_id, ResearchRun.created_at >= since)
    if workspace_id:
        run_query = run_query.where(ResearchRun.workspace_id == workspace_id)
    total_runs, total_cost, mean_duration, total_tokens = db.execute(run_query).one()

    success_query = select(func.count(ResearchRun.id)).where(
        ResearchRun.organization_id == organization_id,
        ResearchRun.created_at >= since,
        ResearchRun.status == "SUCCEEDED",
    )
    accurate_query = select(func.count(Evaluation.id)).where(
        Evaluation.organization_id == organization_id,
        Evaluation.created_at >= since,
        Evaluation.overall_score.is_not(None),
        Evaluation.overall_score >= 80.0,
    )
    if workspace_id:
        success_query = success_query.where(ResearchRun.workspace_id == workspace_id)
        accurate_query = accurate_query.where(Evaluation.workspace_id == workspace_id)
    successful_runs = int(db.scalar(success_query) or 0)
    accurate_answers = int(db.scalar(accurate_query) or 0)

    total_cost = float(total_cost or 0.0)
    total_runs = int(total_runs or 0)
    subscription = subscription_for(db, organization_id)

    return {
        "window_days": days,
        "period_start": since.isoformat(),
        "period_end": now.isoformat(),
        "totals": {
            "research_runs": total_runs,
            "successful_runs": successful_runs,
            "estimated_cost_usd": round(total_cost, 6),
            "total_tokens": int(total_tokens or 0),
            "mean_duration_ms": int(mean_duration or 0),
        },
        "unit_economics": {
            "cost_per_run_usd": round(total_cost / total_runs, 6) if total_runs else 0.0,
            "cost_per_successful_run_usd": (
                round(total_cost / successful_runs, 6) if successful_runs else None
            ),
            "cost_per_accurate_answer_usd": (
                round(total_cost / accurate_answers, 6) if accurate_answers else None
            ),
            "accurate_answers": accurate_answers,
            "accuracy_threshold": 80.0,
            "note": (
                "Costs are estimates from the configured rate card. 'Accurate answer' means an "
                "evaluation scored at or above the threshold, not a market outcome."
            ),
        },
        "by_kind": by_kind,
        "by_model": by_model,
        "plan": {
            "plan": subscription.plan if subscription else None,
            "research_run_limit": subscription.research_run_limit if subscription else None,
            "evaluation_limit": subscription.evaluation_limit if subscription else None,
            "backtest_limit": subscription.backtest_limit if subscription else None,
            "monthly_cost_cap_usd": subscription.monthly_cost_cap_usd if subscription else None,
            "trial_ends_at": (
                subscription.trial_ends_at.isoformat()
                if subscription and subscription.trial_ends_at
                else None
            ),
        },
    }


def cost_trend(
    db: DbSession, *, organization_id: str, workspace_id: str | None = None, days: int = 30
) -> list[dict[str, Any]]:
    """Daily cost and run counts, for the dashboard trend chart."""
    since, _ = period_bounds(days)
    query = select(
        func.date(ResearchRun.created_at),
        func.count(ResearchRun.id),
        func.coalesce(func.sum(ResearchRun.estimated_cost_usd), 0.0),
    ).where(ResearchRun.organization_id == organization_id, ResearchRun.created_at >= since)
    if workspace_id:
        query = query.where(ResearchRun.workspace_id == workspace_id)
    return [
        {"date": str(day), "runs": int(count or 0), "estimated_cost_usd": round(float(cost or 0.0), 6)}
        for day, count, cost in db.execute(
            query.group_by(func.date(ResearchRun.created_at)).order_by(func.date(ResearchRun.created_at))
        )
    ]


def research_efficiency(
    *, mean_score: float, mean_cost_usd: float, mean_duration_ms: int
) -> dict[str, Any]:
    """Platform-defined 'Research Efficiency' metric.

    Quality per unit of cost and time. It is a **platform-defined index**, not a scientific
    measure, and is labelled as such wherever it appears.
    """
    cost_component = max(mean_cost_usd, 0.01)
    time_component = max(mean_duration_ms / 1000.0, 1.0)
    return {
        "value": round(mean_score / (cost_component**0.5 * time_component**0.25), 3),
        "inputs": {
            "mean_score": round(mean_score, 2),
            "mean_cost_usd": round(mean_cost_usd, 6),
            "mean_duration_ms": mean_duration_ms,
        },
        "formula": "mean_score / (sqrt(mean_cost_usd) * mean_duration_seconds^0.25)",
        "disclaimer": (
            "Research Efficiency is a platform-defined index for comparing agents under "
            "identical conditions. It is not a scientific or financial metric."
        ),
    }
