"""Agent builder: agents, immutable versions, prompt history, and the capability catalog."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from finagent_api.db.models import Agent, AgentVersion
from finagent_api.deps import Db, WorkspaceContext, require_permission
from finagent_api.rbac import Permission
from finagent_api.schemas import (
    AgentCreateRequest,
    AgentResponse,
    AgentUpdateRequest,
    AgentVersionResponse,
    Message,
    PromptVersionResponse,
)
from finagent_api.services import agent_service

router = APIRouter(prefix="/agents", tags=["agents"])

ReadAgents = Annotated[WorkspaceContext, Depends(require_permission(Permission.AGENT_READ))]
WriteAgents = Annotated[WorkspaceContext, Depends(require_permission(Permission.AGENT_CREATE))]
UpdateAgents = Annotated[WorkspaceContext, Depends(require_permission(Permission.AGENT_UPDATE))]
DeleteAgents = Annotated[WorkspaceContext, Depends(require_permission(Permission.AGENT_DELETE))]

#: Tool categories for the builder UI. Tools not listed fall back to "other".
_TOOL_CATEGORY = {
    "DOCUMENT_SEARCH": "research",
    "SEC_SEARCH": "research",
    "FINANCIAL_STATEMENTS": "fundamentals",
    "MARKET_DATA": "market",
    "CALCULATOR": "quant",
    "PYTHON": "quant",
    "BACKTEST": "quant",
    "PORTFOLIO_ANALYSIS": "quant",
}
_NETWORK_TOOLS = {"SEC_SEARCH", "MARKET_DATA", "FINANCIAL_STATEMENTS"}
_DETERMINISTIC_TOOLS = {"CALCULATOR", "PYTHON", "BACKTEST", "PORTFOLIO_ANALYSIS"}


def _draft(payload: AgentCreateRequest) -> agent_service.AgentDraft:
    kwargs = payload.model_dump()
    kwargs["output_format"] = payload.output_format.value
    if kwargs.get("instructions") is None:
        kwargs.pop("instructions")
    return agent_service.AgentDraft(**kwargs)


def _version_response(db, version: AgentVersion) -> AgentVersionResponse:
    return AgentVersionResponse.model_validate(version).model_copy(
        update={
            "tools": agent_service.version_tools(db, version.id),
            "bindings": agent_service.version_bindings(db, version.id),
        }
    )


def _agent_response(db, agent: Agent) -> AgentResponse:
    version = None
    if agent.current_version_id:
        current = db.get(AgentVersion, agent.current_version_id)
        version = _version_response(db, current) if current else None
    count = db.scalar(
        select(func.count(AgentVersion.id)).where(AgentVersion.agent_id == agent.id)
    )
    return AgentResponse.model_validate(agent).model_copy(
        update={"current_version": version, "version_count": int(count or 0)}
    )


@router.get("", response_model=list[AgentResponse], summary="List agents")
def list_agents(
    db: Db,
    context: ReadAgents,
    include_deleted: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AgentResponse]:
    query = select(Agent).where(Agent.workspace_id == context.workspace_id)
    if not include_deleted:
        query = query.where(Agent.deleted_at.is_(None))
    rows = db.scalars(query.order_by(Agent.created_at.desc()).limit(limit).offset(offset))
    return [_agent_response(db, agent) for agent in rows]


@router.post(
    "", response_model=AgentResponse, status_code=status.HTTP_201_CREATED, summary="Create an agent"
)
def create_agent(payload: AgentCreateRequest, db: Db, context: WriteAgents) -> AgentResponse:
    agent, _version = agent_service.create_agent(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        draft=_draft(payload),
        user_id=context.user_id,
    )
    return _agent_response(db, agent)


@router.get("/{agent_id}", response_model=AgentResponse, summary="Get an agent")
def get_agent(agent_id: str, db: Db, context: ReadAgents) -> AgentResponse:
    agent = agent_service.get_agent(db, workspace_id=context.workspace_id, agent_id=agent_id)
    return _agent_response(db, agent)


@router.post(
    "/{agent_id}/versions",
    response_model=AgentVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a new immutable version",
)
def create_version(
    agent_id: str, payload: AgentUpdateRequest, db: Db, context: UpdateAgents
) -> AgentVersionResponse:
    """Agents are never edited in place.

    Every configuration change produces a new version with its own ``config_hash``, so a
    past run can always be tied to the exact configuration that produced it.
    """
    agent = agent_service.get_agent(db, workspace_id=context.workspace_id, agent_id=agent_id)
    version = agent_service.create_version(
        db, agent=agent, draft=_draft(payload), user_id=context.user_id
    )
    return _version_response(db, version)


@router.get(
    "/{agent_id}/versions", response_model=list[AgentVersionResponse], summary="Version history"
)
def list_versions(agent_id: str, db: Db, context: ReadAgents) -> list[AgentVersionResponse]:
    agent_service.get_agent(db, workspace_id=context.workspace_id, agent_id=agent_id)
    return [_version_response(db, version) for version in agent_service.list_versions(db, agent_id)]


@router.get(
    "/{agent_id}/prompts", response_model=list[PromptVersionResponse], summary="Prompt history"
)
def list_prompts(agent_id: str, db: Db, context: ReadAgents) -> list[PromptVersionResponse]:
    agent_service.get_agent(db, workspace_id=context.workspace_id, agent_id=agent_id)
    return [
        PromptVersionResponse.model_validate(prompt)
        for prompt in agent_service.list_prompts(db, agent_id)
    ]


@router.delete("/{agent_id}", response_model=Message, summary="Delete an agent")
def delete_agent(agent_id: str, db: Db, context: DeleteAgents) -> Message:
    agent = agent_service.get_agent(db, workspace_id=context.workspace_id, agent_id=agent_id)
    agent_service.soft_delete_agent(db, agent=agent, user_id=context.user_id)
    return Message(
        message="Agent deleted.",
        detail={"note": "Past runs and evaluations remain available for audit."},
    )
