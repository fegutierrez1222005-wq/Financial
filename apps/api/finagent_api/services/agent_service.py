"""Agent builder service.

Versioning rule: an agent's configuration is never mutated. Any change creates
``version_number + 1``, and prompts are versioned independently so a prompt-only change can
be A/B tested against an identical model and tool set.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from finagent_api.db.models import (
    Agent,
    AgentDataset,
    AgentModel,
    AgentPrompt,
    AgentTool,
    AgentVersion,
)
from finagent_api.services.audit import AuditAction, record_audit
from finagent_api.services.providers import resolve_model, tool_registry
from finagent_core.errors import ConflictError, NotFoundError, ValidationFailedError
from finagent_core.logging import get_logger
from finagent_core.models.catalog import MODEL_CATALOG
from finagent_core.schemas.enums import OutputFormat
from finagent_core.schemas.research import AgentRunSpec

logger = get_logger(__name__)

DEFAULT_TOOLS = ["DOCUMENT_SEARCH", "FINANCIAL_STATEMENTS", "CALCULATOR", "MARKET_DATA"]

DEFAULT_INSTRUCTIONS = (
    "You are an institutional equity research analyst. Analyze companies using only the data "
    "sources provided. Every factual claim must have a citation. Clearly distinguish facts "
    "from assumptions."
)


@dataclass
class AgentDraft:
    name: str
    description: str | None = None
    instructions: str = DEFAULT_INSTRUCTIONS
    model: str | None = None
    temperature: float = 0.2
    max_tokens: int = 2048
    max_steps: int = 8
    timeout_seconds: int = 300
    output_format: str = OutputFormat.MARKDOWN.value
    tools: list[str] | None = None
    dataset_ids: list[str] | None = None
    document_ids: list[str] | None = None
    data_source_ids: list[str] | None = None
    evaluation_suite_keys: list[str] | None = None
    risk_constraints: dict[str, Any] | None = None
    archetype: str = "analyst"
    change_note: str | None = None
    is_demo: bool = False


def _config_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _validate_tools(tools: list[str]) -> list[str]:
    known = set(tool_registry().names())
    unknown = [tool for tool in tools if tool not in known]
    if unknown:
        raise ValidationFailedError(
            f"unknown tools: {', '.join(unknown)}", details={"available_tools": sorted(known)}
        )
    return list(dict.fromkeys(tools))


def _validate_output_format(value: str) -> str:
    try:
        return OutputFormat(value).value
    except ValueError as exc:
        raise ValidationFailedError(
            f"unsupported output format: {value}",
            details={"supported": [item.value for item in OutputFormat]},
        ) from exc


def create_agent(
    db: DbSession, *, organization_id: str, workspace_id: str, draft: AgentDraft, user_id: str | None
) -> tuple[Agent, AgentVersion]:
    if not (draft.name or "").strip():
        raise ValidationFailedError("agent name is required")
    if (
        db.scalar(
            select(Agent).where(
                Agent.workspace_id == workspace_id,
                Agent.name == draft.name.strip(),
                Agent.deleted_at.is_(None),
            )
        )
        is not None
    ):
        raise ConflictError("an agent with this name already exists in the workspace")

    agent = Agent(
        organization_id=organization_id,
        workspace_id=workspace_id,
        name=draft.name.strip(),
        description=(draft.description or "").strip() or None,
        archetype=draft.archetype,
        created_by_user_id=user_id,
        is_demo=draft.is_demo,
    )
    db.add(agent)
    db.flush()
    version = create_version(
        db, agent=agent, draft=draft, user_id=user_id, audit_action=AuditAction.AGENT_CREATED
    )
    return agent, version


def create_version(
    db: DbSession,
    *,
    agent: Agent,
    draft: AgentDraft,
    user_id: str | None,
    audit_action: AuditAction = AuditAction.AGENT_VERSION_CREATED,
) -> AgentVersion:
    """Create the next immutable version of ``agent``."""
    tools = _validate_tools(draft.tools if draft.tools is not None else DEFAULT_TOOLS)
    output_format = _validate_output_format(draft.output_format)
    model_key = resolve_model(draft.model)
    if not (0.0 <= draft.temperature <= 2.0):
        raise ValidationFailedError("temperature must be between 0.0 and 2.0")
    if not (1 <= draft.max_steps <= 40):
        raise ValidationFailedError("max_steps must be between 1 and 40")

    prompt = _ensure_prompt_version(db, agent=agent, content=draft.instructions, user_id=user_id)
    next_number = (
        int(
            db.scalar(
                select(func.coalesce(func.max(AgentVersion.version_number), 0)).where(
                    AgentVersion.agent_id == agent.id
                )
            )
            or 0
        )
        + 1
    )

    version = AgentVersion(
        organization_id=agent.organization_id,
        workspace_id=agent.workspace_id,
        agent_id=agent.id,
        version_number=next_number,
        prompt_version_id=prompt.id,
        model=model_key,
        temperature=draft.temperature,
        max_tokens=draft.max_tokens,
        max_steps=draft.max_steps,
        timeout_seconds=draft.timeout_seconds,
        output_format=output_format,
        risk_constraints=draft.risk_constraints or {},
        evaluation_suite_keys=draft.evaluation_suite_keys or [],
        change_note=draft.change_note,
        created_by_user_id=user_id,
        config_hash=_config_hash(
            {
                "model": model_key,
                "temperature": draft.temperature,
                "max_tokens": draft.max_tokens,
                "max_steps": draft.max_steps,
                "output_format": output_format,
                "tools": sorted(tools),
                "prompt_hash": prompt.content_hash,
                "dataset_ids": sorted(draft.dataset_ids or []),
                "document_ids": sorted(draft.document_ids or []),
                "data_source_ids": sorted(draft.data_source_ids or []),
                "risk_constraints": draft.risk_constraints or {},
            }
        ),
    )
    db.add(version)
    db.flush()

    for tool_name in tools:
        tool = tool_registry().get(tool_name)
        db.add(
            AgentTool(
                organization_id=agent.organization_id,
                workspace_id=agent.workspace_id,
                agent_version_id=version.id,
                tool_name=tool_name,
                permissions=[permission.value for permission in tool.required_permissions],
                config={},
            )
        )

    info = MODEL_CATALOG.get(model_key)
    db.add(
        AgentModel(
            organization_id=agent.organization_id,
            workspace_id=agent.workspace_id,
            agent_version_id=version.id,
            provider=info.provider if info else "unknown",
            model_key=model_key,
            role="primary",
            parameters={"temperature": draft.temperature, "max_tokens": draft.max_tokens},
        )
    )

    for kind, ids in (
        ("dataset", draft.dataset_ids or []),
        ("document", draft.document_ids or []),
        ("data_source", draft.data_source_ids or []),
    ):
        for identifier in ids:
            db.add(
                AgentDataset(
                    organization_id=agent.organization_id,
                    workspace_id=agent.workspace_id,
                    agent_version_id=version.id,
                    dataset_id=identifier if kind == "dataset" else None,
                    document_id=identifier if kind == "document" else None,
                    data_source_id=identifier if kind == "data_source" else None,
                    binding_kind=kind,
                )
            )

    agent.current_version_id = version.id
    if draft.description is not None:
        agent.description = (draft.description or "").strip() or None
    db.flush()

    record_audit(
        db,
        action=audit_action,
        organization_id=agent.organization_id,
        workspace_id=agent.workspace_id,
        user_id=user_id,
        resource_type="agent_version",
        resource_id=version.id,
        metadata={
            "agent_id": agent.id,
            "version_number": next_number,
            "model": model_key,
            "tools": tools,
            "prompt_version": prompt.version_number,
        },
    )
    logger.info(
        "agent_version_created",
        extra={"agent_id": agent.id, "version": next_number, "model": model_key},
    )
    return version


def _ensure_prompt_version(
    db: DbSession, *, agent: Agent, content: str, user_id: str | None
) -> AgentPrompt:
    """Reuse the latest prompt when unchanged; otherwise create the next version."""
    cleaned = (content or DEFAULT_INSTRUCTIONS).strip()
    if len(cleaned) < 20:
        raise ValidationFailedError("agent instructions must be at least 20 characters")
    content_hash = hashlib.sha256(cleaned.encode()).hexdigest()

    latest = db.scalar(
        select(AgentPrompt)
        .where(AgentPrompt.agent_id == agent.id)
        .order_by(AgentPrompt.version_number.desc())
        .limit(1)
    )
    if latest is not None and latest.content_hash == content_hash:
        return latest

    prompt = AgentPrompt(
        organization_id=agent.organization_id,
        workspace_id=agent.workspace_id,
        agent_id=agent.id,
        version_number=(latest.version_number + 1) if latest else 1,
        content=cleaned,
        content_hash=content_hash,
        created_by_user_id=user_id,
    )
    db.add(prompt)
    db.flush()
    record_audit(
        db,
        action=AuditAction.PROMPT_VERSION_CREATED,
        organization_id=agent.organization_id,
        workspace_id=agent.workspace_id,
        user_id=user_id,
        resource_type="agent_prompt",
        resource_id=prompt.id,
        metadata={"agent_id": agent.id, "version_number": prompt.version_number},
    )
    return prompt


def get_agent(db: DbSession, *, workspace_id: str, agent_id: str) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None or agent.workspace_id != workspace_id or agent.deleted_at is not None:
        raise NotFoundError("agent not found")
    return agent


def get_version(db: DbSession, *, workspace_id: str, version_id: str) -> AgentVersion:
    version = db.get(AgentVersion, version_id)
    if version is None or version.workspace_id != workspace_id:
        raise NotFoundError("agent version not found")
    return version


def current_version(db: DbSession, agent: Agent) -> AgentVersion:
    if agent.current_version_id:
        version = db.get(AgentVersion, agent.current_version_id)
        if version is not None:
            return version
    version = db.scalar(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent.id)
        .order_by(AgentVersion.version_number.desc())
        .limit(1)
    )
    if version is None:
        raise NotFoundError("agent has no versions")
    return version


def list_versions(db: DbSession, agent_id: str) -> list[AgentVersion]:
    return list(
        db.scalars(
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.version_number.desc())
        )
    )


def list_prompts(db: DbSession, agent_id: str) -> list[AgentPrompt]:
    return list(
        db.scalars(
            select(AgentPrompt)
            .where(AgentPrompt.agent_id == agent_id)
            .order_by(AgentPrompt.version_number.desc())
        )
    )


def version_tools(db: DbSession, version_id: str) -> list[str]:
    return [
        row.tool_name
        for row in db.scalars(select(AgentTool).where(AgentTool.agent_version_id == version_id))
    ]


def version_bindings(db: DbSession, version_id: str) -> dict[str, list[str]]:
    bindings: dict[str, list[str]] = {"dataset": [], "document": [], "data_source": []}
    for row in db.scalars(select(AgentDataset).where(AgentDataset.agent_version_id == version_id)):
        identifier = row.dataset_id or row.document_id or row.data_source_id
        if identifier:
            bindings.setdefault(row.binding_kind, []).append(identifier)
    return bindings


def build_run_spec(
    db: DbSession,
    *,
    agent: Agent,
    version: AgentVersion,
    information_cutoff=None,
    model_override: str | None = None,
    output_format_override: str | None = None,
) -> AgentRunSpec:
    """Assemble the immutable execution spec recorded on every run."""
    prompt = db.get(AgentPrompt, version.prompt_version_id) if version.prompt_version_id else None
    bindings = version_bindings(db, version.id)
    return AgentRunSpec(
        agent_id=agent.id,
        agent_version_id=version.id,
        agent_name=agent.name,
        version_number=version.version_number,
        model=model_override or version.model,
        temperature=version.temperature,
        max_tokens=version.max_tokens,
        max_steps=version.max_steps,
        timeout_seconds=version.timeout_seconds,
        system_prompt=prompt.content if prompt else DEFAULT_INSTRUCTIONS,
        prompt_version_id=prompt.id if prompt else None,
        prompt_version_number=prompt.version_number if prompt else 1,
        tools=version_tools(db, version.id),
        dataset_ids=bindings.get("dataset", []),
        document_ids=bindings.get("document", []),
        output_format=output_format_override or version.output_format,
        risk_constraints=version.risk_constraints or {},
        information_cutoff=information_cutoff,
    )


def soft_delete_agent(db: DbSession, *, agent: Agent, user_id: str | None) -> None:
    from finagent_api.db.base import utcnow

    agent.deleted_at = utcnow()
    db.flush()
    record_audit(
        db,
        action=AuditAction.AGENT_DELETED,
        organization_id=agent.organization_id,
        workspace_id=agent.workspace_id,
        user_id=user_id,
        resource_type="agent",
        resource_id=agent.id,
    )
