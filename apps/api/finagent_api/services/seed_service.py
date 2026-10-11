"""Demo seeding.

Creates a workspace that is immediately usable without external credentials: the labelled
ACME Technologies corpus, the built-in golden suite, two agents (one deliberately flawed for
demonstrating failure detection), data-source records and a backtest configuration.

Everything created here is marked ``is_demo=True`` and surfaces a ``DEMO`` badge in the UI.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from finagent_api.db.models import (
    Agent,
    Backtest,
    DataSource,
    Document,
    DocumentChunk,
    Organization,
    User,
    Workspace,
)
from finagent_api.services import agent_service, evaluation_service, workspace_service
from finagent_api.services.agent_service import AgentDraft
from finagent_api.services.audit import AuditAction, record_audit
from finagent_api.services.backtest_service import BacktestDraft, create_backtest
from finagent_api.services.document_service import upload_document
from finagent_api.services.providers import data_registry
from finagent_core.data.demo_dataset import DEMO_UNIVERSE, demo_documents
from finagent_core.logging import get_logger
from finagent_core.schemas.enums import OutputFormat, WorkspaceRole

logger = get_logger(__name__)

DEMO_WORKSPACE_NAME = "ACME Demo Research"
DEMO_AGENT_NAME = "Equity Research Analyst (demo)"
FLAWED_AGENT_NAME = "Unreliable Analyst (demo fixture)"

FLAWED_AGENT_NOTE = (
    "Deliberately flawed demo fixture. It omits citations and asserts an unsupported growth "
    "figure so the evaluation engine's hallucination detection can be demonstrated. Never use it "
    "for research."
)


def seed_demo_workspace(
    db: DbSession, *, organization: Organization, user: User, workspace: Workspace | None = None
) -> dict[str, Any]:
    """Idempotent: re-running adds only what is missing."""
    workspace = workspace or workspace_service.create_workspace(
        db,
        organization=organization,
        name=DEMO_WORKSPACE_NAME,
        creator=user,
        description=(
            "Demo workspace containing the fictional issuer ACME Technologies. All data here is "
            "synthetic and labelled DEMO."
        ),
        use_case="demo",
        role=WorkspaceRole.OWNER,
        is_demo=True,
    )

    documents = _seed_documents(db, organization=organization, workspace=workspace, user=user)
    suites = evaluation_service.install_builtin_suites(
        db, organization_id=organization.id, workspace_id=workspace.id
    )
    data_source = _seed_data_sources(db, organization=organization, workspace=workspace)
    agents = _seed_agents(db, organization=organization, workspace=workspace, user=user)
    backtest = _seed_backtest(db, organization=organization, workspace=workspace, user=user)

    record_audit(
        db,
        action=AuditAction.DEMO_SEEDED,
        organization_id=organization.id,
        workspace_id=workspace.id,
        user_id=user.id,
        resource_type="workspace",
        resource_id=workspace.id,
        metadata={
            "documents": len(documents),
            "suites": [suite.key for suite in suites],
            "agents": [agent.name for agent in agents],
        },
    )
    logger.info(
        "demo_workspace_seeded",
        extra={"workspace_id": workspace.id, "documents": len(documents), "agents": len(agents)},
    )
    return {
        "workspace_id": workspace.id,
        "workspace_name": workspace.name,
        "documents": [document.id for document in documents],
        "document_count": len(documents),
        "evaluation_suites": [suite.key for suite in suites],
        "agents": [{"id": agent.id, "name": agent.name} for agent in agents],
        "data_source_id": data_source.id if data_source else None,
        "backtest_id": backtest.id if backtest else None,
        "disclaimer": (
            "ACME Technologies is a fictional issuer. Every figure in this workspace is synthetic "
            "and must not be used for investment decisions."
        ),
    }


def _seed_documents(
    db: DbSession, *, organization: Organization, workspace: Workspace, user: User
) -> list[Document]:
    created: list[Document] = []
    for demo in demo_documents():
        existing = db.scalar(
            select(Document).where(
                Document.workspace_id == workspace.id,
                Document.filename == f"{demo.key}.txt",
                Document.deleted_at.is_(None),
            )
        )
        if existing is not None:
            created.append(existing)
            continue
        document = upload_document(
            db,
            organization_id=organization.id,
            workspace_id=workspace.id,
            payload=demo.text.encode("utf-8"),
            filename=f"{demo.key}.txt",
            user_id=user.id,
            publication_timestamp=demo.filed_at,
            source_label=demo.source_label,
            document_type=demo.form_type,
            ticker=demo.ticker,
            title=demo.title,
            is_demo=True,
            persist_file=False,
        )
        # Demo pages carry their own numbering (an excerpt may start at page 42); reapply it
        # so citations match the source document rather than synthetic chunk order.
        _reapply_demo_page_numbers(db, document=document, demo=demo)
        created.append(document)
    return created


def _reapply_demo_page_numbers(db: DbSession, *, document: Document, demo) -> None:
    chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index)
        )
    )
    page_numbers = [page.page_number for page in demo.pages]
    page_texts = [page.text for page in demo.pages]
    for chunk in chunks:
        opening = chunk.text[:40]
        for index, text in enumerate(page_texts):
            if opening and opening in text:
                chunk.page_number = page_numbers[index]
                break
    document.page_count = max(page_numbers)
    db.flush()


def _seed_data_sources(
    db: DbSession, *, organization: Organization, workspace: Workspace
) -> DataSource | None:
    demo_source: DataSource | None = None
    for descriptor in data_registry().describe():
        existing = db.scalar(
            select(DataSource).where(
                DataSource.workspace_id == workspace.id,
                DataSource.provider_key == descriptor["key"],
            )
        )
        if existing is not None:
            existing.status = descriptor["status"]
            existing.capabilities = descriptor["capabilities"]
            if descriptor["is_demo"]:
                demo_source = demo_source or existing
            continue
        source = DataSource(
            organization_id=organization.id,
            workspace_id=workspace.id,
            provider_key=descriptor["key"],
            name=descriptor["display_name"],
            kind="market_data",
            status=descriptor["status"],
            is_demo=descriptor["is_demo"],
            capabilities=descriptor["capabilities"],
            config={"requires_credentials": descriptor["requires_credentials"]},
            last_checked_at=datetime.now(UTC),
        )
        db.add(source)
        db.flush()
        if descriptor["is_demo"]:
            demo_source = source
    return demo_source


def _seed_agents(
    db: DbSession, *, organization: Organization, workspace: Workspace, user: User
) -> list[Agent]:
    agents: list[Agent] = []

    for name, draft in (
        (
            DEMO_AGENT_NAME,
            AgentDraft(
                name=DEMO_AGENT_NAME,
                description="Institutional equity research analyst configured for the ACME demo corpus.",
                instructions=(
                    "You are an institutional equity research analyst. Analyze companies using only "
                    "the data sources provided. Every factual claim must have a citation. Clearly "
                    "distinguish facts from assumptions. Recompute every derived figure with a tool "
                    "rather than asserting it."
                ),
                model="mock-analyst-v1",
                tools=[
                    "DOCUMENT_SEARCH",
                    "FINANCIAL_STATEMENTS",
                    "MARKET_DATA",
                    "CALCULATOR",
                    "PYTHON",
                    "SEC_SEARCH",
                    "BACKTEST",
                    "PORTFOLIO_ANALYSIS",
                ],
                evaluation_suite_keys=["FINANCIAL_RESEARCH_BASIC_V1"],
                output_format=OutputFormat.MARKDOWN.value,
                risk_constraints={"max_position_pct": 3.0, "no_trade_recommendations": True},
                is_demo=True,
                change_note="Seeded demo agent.",
            ),
        ),
        (
            FLAWED_AGENT_NAME,
            AgentDraft(
                name=FLAWED_AGENT_NAME,
                description=FLAWED_AGENT_NOTE,
                instructions=(
                    "You are a confident analyst. Produce a decisive answer quickly. (Demo fixture: "
                    "this configuration intentionally under-specifies evidence requirements so the "
                    "evaluation engine can be shown catching failures.)"
                ),
                model="mock-analyst-weak",
                tools=["DOCUMENT_SEARCH", "FINANCIAL_STATEMENTS", "CALCULATOR"],
                evaluation_suite_keys=["FINANCIAL_RESEARCH_BASIC_V1"],
                is_demo=True,
                change_note="Seeded flawed comparison fixture.",
            ),
        ),
    ):
        existing = db.scalar(
            select(Agent).where(
                Agent.workspace_id == workspace.id, Agent.name == name, Agent.deleted_at.is_(None)
            )
        )
        if existing is not None:
            agents.append(existing)
            continue
        agent, _ = agent_service.create_agent(
            db,
            organization_id=organization.id,
            workspace_id=workspace.id,
            user_id=user.id,
            draft=draft,
        )
        agents.append(agent)
    return agents


def _seed_backtest(db: DbSession, *, organization: Organization, workspace: Workspace, user: User):
    existing = db.scalar(
        select(Backtest).where(
            Backtest.workspace_id == workspace.id,
            Backtest.name == "Demo momentum, 8-name universe",
            Backtest.deleted_at.is_(None),
        )
    )
    if existing is not None:
        return existing
    return create_backtest(
        db,
        organization_id=organization.id,
        workspace_id=workspace.id,
        user_id=user.id,
        draft=BacktestDraft(
            name="Demo momentum, 8-name universe",
            description=(
                "Six-month cross-sectional momentum on the synthetic demo universe, with a one-bar "
                "signal lag, 10bps commission and 5bps slippage. Runs on DEMO data."
            ),
            universe=list(DEMO_UNIVERSE),
            start_date=date(2019, 1, 2),
            end_date=date(2024, 6, 28),
            strategy_kind="cross_sectional_momentum",
            lookback_days=126,
            top_n=3,
            use_splits=True,
        ),
    )
