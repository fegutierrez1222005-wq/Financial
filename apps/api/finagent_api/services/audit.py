"""Audit logging.

Every security- and research-relevant action is recorded with actor, tenant, resource, IP
and request id. Writes are best-effort: a logging failure must never block the operation it
describes, but it is always reported in the application log.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session as DbSession

from finagent_api.db.models import AuditLog
from finagent_core.logging import get_logger, redact

logger = get_logger(__name__)


class AuditAction(StrEnum):
    LOGIN = "auth.login"
    LOGIN_FAILED = "auth.login_failed"
    LOGOUT = "auth.logout"
    SIGNUP = "auth.signup"
    MFA_ENABLED = "auth.mfa_enabled"
    MFA_DISABLED = "auth.mfa_disabled"
    PASSWORD_CHANGED = "auth.password_changed"

    ORGANIZATION_CREATED = "organization.created"
    ORGANIZATION_UPDATED = "organization.updated"
    WORKSPACE_CREATED = "workspace.created"
    WORKSPACE_UPDATED = "workspace.updated"
    WORKSPACE_DELETED = "workspace.deleted"
    MEMBER_INVITED = "member.invited"
    MEMBER_ADDED = "member.added"
    MEMBER_ROLE_CHANGED = "member.role_changed"
    MEMBER_REMOVED = "member.removed"

    AGENT_CREATED = "agent.created"
    AGENT_VERSION_CREATED = "agent.version_created"
    PROMPT_VERSION_CREATED = "agent.prompt_version_created"
    AGENT_DELETED = "agent.deleted"

    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_DELETED = "document.deleted"
    DATASET_CREATED = "dataset.created"
    DATA_SOURCE_UPDATED = "data_source.updated"

    RESEARCH_RUN_STARTED = "research.run_started"
    RESEARCH_RUN_COMPLETED = "research.run_completed"
    RESEARCH_RUN_FAILED = "research.run_failed"
    RESEARCH_RUN_REPRODUCED = "research.run_reproduced"
    DEBATE_STARTED = "research.debate_started"

    EVALUATION_STARTED = "evaluation.started"
    EVALUATION_COMPLETED = "evaluation.completed"
    EVALUATION_SUITE_CREATED = "evaluation.suite_created"

    BACKTEST_CREATED = "backtest.created"
    BACKTEST_RUN_COMPLETED = "backtest.run_completed"

    EXPERIMENT_CREATED = "experiment.created"
    BENCHMARK_CREATED = "benchmark.created"

    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"
    WEBHOOK_CREATED = "webhook.created"
    WEBHOOK_DELETED = "webhook.deleted"
    PERMISSION_CHANGED = "permission.changed"
    SETTINGS_UPDATED = "settings.updated"
    DEMO_SEEDED = "workspace.demo_seeded"


def record_audit(
    db: DbSession,
    *,
    action: AuditAction | str,
    organization_id: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
    api_key_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    outcome: str = "SUCCESS",
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog | None:
    entry = AuditLog(
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        api_key_id=api_key_id,
        action=str(action),
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        outcome=outcome,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:400] or None,
        request_id=request_id,
        metadata_json=redact(metadata or {}),
    )
    try:
        db.add(entry)
        db.flush()
    except Exception:
        logger.exception("audit_write_failed", extra={"action": str(action)})
        return None
    logger.info(
        "audit",
        extra={
            "action": str(action),
            "resource_type": resource_type,
            "resource_id": resource_id,
            "outcome": outcome,
        },
    )
    return entry


def audit_from_context(context: Any, db: DbSession, **kwargs: Any) -> AuditLog | None:
    """Convenience wrapper for routes holding a :class:`WorkspaceContext`."""
    principal = context.principal
    return record_audit(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        user_id=principal.user_id,
        api_key_id=principal.api_key.id if principal.api_key else None,
        ip_address=principal.ip_address,
        user_agent=principal.user_agent,
        request_id=principal.request_id,
        **kwargs,
    )


def list_audit_logs(
    db: DbSession,
    *,
    organization_id: str,
    workspace_id: str | None = None,
    action: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    query = select(AuditLog).where(AuditLog.organization_id == organization_id)
    if workspace_id:
        query = query.where(AuditLog.workspace_id == workspace_id)
    if action:
        query = query.where(AuditLog.action == action)
    return list(db.scalars(query.order_by(desc(AuditLog.created_at)).limit(min(limit, 500)).offset(offset)))
