"""The first demo flow, end to end, with no HTTP layer.

Seeds the ACME Technologies workspace, runs the demo analyst on a question whose answer is
derivable from the seeded filings, scores the run, runs the same question against the
deliberately flawed fixture agent so the evaluators can be seen catching a fabrication, and
executes a backtest on the seeded price series.

Everything here is clearly labelled demo data about a fictional issuer. It exists to prove
the pipeline works, not to suggest anything about a real company.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session as DbSession

from finagent_api.db.models import Organization, OrganizationMember, User
from finagent_api.services import (
    agent_service,
    backtest_service,
    evaluation_service,
    research_service,
    seed_service,
    workspace_service,
)
from finagent_core.logging import get_logger
from finagent_core.schemas.enums import TaskTemplate

logger = get_logger(__name__)

DEMO_QUESTION = (
    "What was ACME Technologies' FY2023 revenue growth, and what drove it? "
    "Cite the filings you used."
)
#: Mid-2023: the FY2023 10-K did not exist yet, so a correct agent must decline to use it.
HISTORICAL_CUTOFF = datetime(2023, 6, 30, tzinfo=timezone.utc)


def run_demo_flow(
    db: DbSession, *, email: str = "demo@finagent.local", password: str = "demo-password-123"
) -> dict[str, Any]:
    from finagent_api.services.auth_service import CredentialAuthProvider

    provider = CredentialAuthProvider(db)
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None:
        user = provider.register(email=email, password=password, full_name="Demo Analyst")
        organization = workspace_service.create_organization(
            db, name="Demo Capital Partners", owner=user
        )
    else:
        organization = (
            db.query(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .filter(OrganizationMember.user_id == user.id)
            .first()
        )

    seeded = seed_service.seed_demo_workspace(db, organization=organization, user=user)
    workspace_id = seeded["workspace_id"]
    db.flush()

    good_agent = agent_service.get_agent(
        db, workspace_id=workspace_id, agent_id=seeded["agent_ids"][0]
    )
    flawed_agent = (
        agent_service.get_agent(db, workspace_id=workspace_id, agent_id=seeded["agent_ids"][1])
        if len(seeded["agent_ids"]) > 1
        else None
    )

    results: dict[str, Any] = {"workspace_id": workspace_id, "notice": seeded["notice"]}
    results["good_agent"] = _run_and_score(
        db,
        organization_id=organization.id,
        workspace_id=workspace_id,
        agent=good_agent,
        user_id=user.id,
        cutoff=None,
    )
    if flawed_agent is not None:
        results["flawed_agent"] = _run_and_score(
            db,
            organization_id=organization.id,
            workspace_id=workspace_id,
            agent=flawed_agent,
            user_id=user.id,
            cutoff=None,
        )
    results["historical_run"] = _run_and_score(
        db,
        organization_id=organization.id,
        workspace_id=workspace_id,
        agent=good_agent,
        user_id=user.id,
        cutoff=HISTORICAL_CUTOFF,
    )

    if seeded.get("backtest_id"):
        runs = backtest_service.execute_backtest(
            db, backtest_id=seeded["backtest_id"], user_id=user.id
        )
        results["backtest"] = {
            "backtest_id": seeded["backtest_id"],
            "splits": [
                {
                    "split": run.split,
                    "is_valid": run.is_valid,
                    "metrics": run.metrics_summary,
                    "findings": run.findings,
                }
                for run in runs
            ],
        }

    return results


def _run_and_score(
    db: DbSession,
    *,
    organization_id: str,
    workspace_id: str,
    agent,  # noqa: ANN001
    user_id: str,
    cutoff: datetime | None,
) -> dict[str, Any]:
    task = research_service.create_task(
        db,
        organization_id=organization_id,
        workspace_id=workspace_id,
        draft=research_service.TaskDraft(
            template=TaskTemplate.EARNINGS_ANALYSIS.value,
            question=DEMO_QUESTION,
            inputs={"ticker": "ACME", "period": "FY2023"},
            information_cutoff=cutoff,
        ),
        user_id=user_id,
    )
    version = agent_service.current_version(db, agent)
    run = research_service.create_run(
        db,
        organization_id=organization_id,
        workspace_id=workspace_id,
        task=task,
        agent=agent,
        version=version,
        user_id=user_id,
    )
    research_service.execute_run(db, run.id)

    evaluation = evaluation_service.create_evaluation(
        db,
        organization_id=organization_id,
        workspace_id=workspace_id,
        kind="run",
        run_id=run.id,
        agent_id=agent.id,
        agent_version_id=version.id,
        user_id=user_id,
    )
    evaluation_service.evaluate_run(db, evaluation_id=evaluation.id)
    detail = evaluation_service.evaluation_detail(db, evaluation)

    return {
        "agent": agent.name,
        "run_id": run.id,
        "information_cutoff": cutoff.isoformat() if cutoff else None,
        "status": run.status,
        "used_mock_model": run.used_mock_model,
        "used_demo_data": run.used_demo_data,
        "evidence_count": run.evidence_count,
        "output_text": run.output_text,
        "evaluation_id": evaluation.id,
        "overall_score": evaluation.overall_score,
        "citation_coverage": evaluation.citation_coverage,
        "hallucination_rate": evaluation.hallucination_rate,
        "scores": detail["scores"],
        "failures": [
            {
                "code": result["failure_code"],
                "title": result["failure_title"],
                "reason": result["failure_reason"],
                "severity": result["severity"],
            }
            for result in detail["results"]
            if not result["passed"]
        ],
    }
