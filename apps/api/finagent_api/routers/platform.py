"""Observability, billing surface, webhooks, notifications, alerts, feedback and admin."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from finagent_api.db.models import Alert, FeedbackEntry, Subscription, Webhook
from finagent_api.deps import (
    CurrentPrincipal,
    Db,
    WorkspaceContext,
    require_permission,
    require_platform_admin,
)
from finagent_api.rbac import Permission
from finagent_api.schemas import (
    AlertCreateRequest,
    AlertResponse,
    AuditLogResponse,
    FeedbackRequest,
    Message,
    ModelDescriptor,
    NotificationResponse,
    SubscriptionResponse,
    ToolDescriptor,
    WebhookCreatedResponse,
    WebhookCreateRequest,
    WebhookResponse,
)
from finagent_api.security.crypto import encrypt_secret
from finagent_api.security.tokens import create_refresh_token
from finagent_api.services import dashboard_service, notification_service, usage_service
from finagent_api.services.audit import AuditAction, list_audit_logs, record_audit
from finagent_api.services.providers import model_registry, tool_registry
from finagent_api.settings import get_settings
from finagent_core.errors import NotFoundError
from finagent_core.models.catalog import MODEL_CATALOG

router = APIRouter(tags=["platform"])

ReadWorkspace = Annotated[WorkspaceContext, Depends(require_permission(Permission.WORKSPACE_READ))]
ReadUsage = Annotated[WorkspaceContext, Depends(require_permission(Permission.USAGE_READ))]
ReadAudit = Annotated[WorkspaceContext, Depends(require_permission(Permission.AUDIT_READ))]
ReadWebhooks = Annotated[WorkspaceContext, Depends(require_permission(Permission.WEBHOOK_READ))]
WriteWebhooks = Annotated[WorkspaceContext, Depends(require_permission(Permission.WEBHOOK_WRITE))]
ReadBilling = Annotated[WorkspaceContext, Depends(require_permission(Permission.BILLING_READ))]
WriteSecurity = Annotated[WorkspaceContext, Depends(require_permission(Permission.SECURITY_WRITE))]

#: Tool metadata for the agent builder. Keys are tool names from the registry.
_TOOL_CATEGORY = {
    "DOCUMENT_SEARCH": ("Internal document search", "research"),
    "SEC_SEARCH": ("SEC EDGAR filing search", "research"),
    "FINANCIAL_STATEMENTS": ("Financial statements", "fundamentals"),
    "MARKET_DATA": ("Market prices", "market"),
    "CALCULATOR": ("Financial calculator", "quant"),
    "PYTHON": ("Sandboxed Python", "quant"),
    "BACKTEST": ("Strategy backtest", "quant"),
    "PORTFOLIO_ANALYSIS": ("Portfolio analysis", "quant"),
}
_NETWORK_TOOLS = {"SEC_SEARCH", "MARKET_DATA", "FINANCIAL_STATEMENTS"}
_DETERMINISTIC_TOOLS = {"CALCULATOR", "PYTHON", "BACKTEST", "PORTFOLIO_ANALYSIS", "DOCUMENT_SEARCH"}


# ------------------------------------------------------------------------ catalog


@router.get("/catalog/models", response_model=list[ModelDescriptor], summary="Model catalog")
def catalog_models() -> list[ModelDescriptor]:
    available = set(model_registry().available_models())
    return [
        ModelDescriptor(
            key=info.key,
            provider=info.provider,
            display_name=info.display_name,
            context_window=info.context_window,
            input_cost_per_1k=info.input_cost_per_1k,
            output_cost_per_1k=info.output_cost_per_1k,
            supports_tools=info.supports_tools,
            available=info.key in available,
            is_mock=info.provider == "mock",
            notes=info.notes or None,
        )
        for info in MODEL_CATALOG.values()
    ]


@router.get("/catalog/tools", response_model=list[ToolDescriptor], summary="Tool catalog")
def catalog_tools() -> list[ToolDescriptor]:
    from finagent_api.services.providers import data_registry

    data_available = {
        entry["key"]: entry["status"] == "available" for entry in data_registry().describe()
    }
    network_ready = any(data_available.values())

    descriptors: list[ToolDescriptor] = []
    for tool in tool_registry().describe():
        name = tool["name"]
        title, category = _TOOL_CATEGORY.get(name, (name.replace("_", " ").title(), "other"))
        needs_network = name in _NETWORK_TOOLS
        available = network_ready if needs_network else True
        descriptors.append(
            ToolDescriptor(
                name=name,
                title=title,
                description=tool["description"],
                category=category,
                requires_network=needs_network,
                is_deterministic=name in _DETERMINISTIC_TOOLS,
                available=available,
                unavailable_reason=(
                    None if available else "no external data provider is configured"
                ),
            )
        )
    return descriptors


# ---------------------------------------------------------------- observability


@router.get("/dashboard", summary="Workspace dashboard")
def dashboard(
    db: Db, context: ReadWorkspace, days: int = Query(default=30, ge=1, le=365)
) -> dict[str, Any]:
    return dashboard_service.workspace_dashboard(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        days=days,
    )


@router.get("/usage", summary="Usage and cost observability")
def usage(
    db: Db, context: ReadUsage, days: int = Query(default=30, ge=1, le=365)
) -> dict[str, Any]:
    return usage_service.usage_summary(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        days=days,
    )


@router.get("/usage/trend", summary="Daily cost trend")
def usage_trend(
    db: Db, context: ReadUsage, days: int = Query(default=30, ge=1, le=365)
) -> list[dict[str, Any]]:
    return usage_service.cost_trend(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        days=days,
    )


@router.get("/audit-logs", response_model=list[AuditLogResponse], summary="Audit log")
def audit_logs(
    db: Db,
    context: ReadAudit,
    action: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLogResponse]:
    rows = list_audit_logs(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    return [AuditLogResponse.model_validate(row) for row in rows]


# -------------------------------------------------------------------- billing


@router.get("/subscription", response_model=SubscriptionResponse, summary="Plan and limits")
def subscription(db: Db, context: ReadBilling) -> SubscriptionResponse:
    row = db.scalar(
        select(Subscription).where(Subscription.organization_id == context.organization_id)
    )
    if row is None:
        raise NotFoundError("no subscription for this organization")
    return SubscriptionResponse.model_validate(row)


# -------------------------------------------------------------------- webhooks


@router.get("/webhooks", response_model=list[WebhookResponse], summary="Webhooks")
def list_webhooks(db: Db, context: ReadWebhooks) -> list[WebhookResponse]:
    rows = db.scalars(
        select(Webhook)
        .where(Webhook.workspace_id == context.workspace_id)
        .order_by(Webhook.created_at.desc())
    )
    return [WebhookResponse.model_validate(row) for row in rows]


@router.post(
    "/webhooks",
    response_model=WebhookCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a webhook (signing secret returned once)",
)
def create_webhook(
    payload: WebhookCreateRequest, db: Db, context: WriteWebhooks
) -> WebhookCreatedResponse:
    secret, _hash = create_refresh_token()
    hook = Webhook(
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        url=payload.url,
        description=payload.description,
        events=payload.events,
        secret_encrypted=encrypt_secret(secret),
        created_by_user_id=context.user_id,
    )
    db.add(hook)
    db.flush()
    record_audit(
        db,
        action=AuditAction.WEBHOOK_CREATED,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        user_id=context.user_id,
        resource_type="webhook",
        resource_id=hook.id,
        metadata={"events": payload.events},
    )
    return WebhookCreatedResponse(
        **WebhookResponse.model_validate(hook).model_dump(), signing_secret=secret
    )


@router.delete("/webhooks/{webhook_id}", response_model=Message, summary="Delete a webhook")
def delete_webhook(webhook_id: str, db: Db, context: WriteWebhooks) -> Message:
    hook = db.get(Webhook, webhook_id)
    if hook is None or hook.workspace_id != context.workspace_id:
        raise NotFoundError("webhook not found")
    db.delete(hook)
    record_audit(
        db,
        action=AuditAction.WEBHOOK_DELETED,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        user_id=context.user_id,
        resource_type="webhook",
        resource_id=webhook_id,
    )
    return Message(message="Webhook deleted.")


# --------------------------------------------------------- notifications & alerts


@router.get(
    "/notifications", response_model=list[NotificationResponse], summary="Notifications"
)
def notifications(
    db: Db, context: ReadWorkspace, limit: int = Query(default=50, ge=1, le=200)
) -> list[NotificationResponse]:
    rows = notification_service.list_notifications(
        db, organization_id=context.organization_id, user_id=context.user_id, limit=limit
    )
    return [NotificationResponse.model_validate(row) for row in rows]


@router.post(
    "/notifications/{notification_id}/read", response_model=Message, summary="Mark as read"
)
def mark_notification_read(
    notification_id: str, db: Db, context: ReadWorkspace
) -> Message:
    updated = notification_service.mark_read(
        db, notification_id=notification_id, organization_id=context.organization_id
    )
    if updated is None:
        raise NotFoundError("notification not found")
    return Message(message="Notification marked read.")


@router.get("/alerts", response_model=list[AlertResponse], summary="Quality alerts")
def list_alerts(db: Db, context: ReadWorkspace) -> list[AlertResponse]:
    rows = db.scalars(
        select(Alert).where(Alert.workspace_id == context.workspace_id).order_by(Alert.name)
    )
    return [AlertResponse.model_validate(row) for row in rows]


@router.post(
    "/alerts",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a quality alert",
)
def create_alert(payload: AlertCreateRequest, db: Db, context: WriteSecurity) -> AlertResponse:
    alert = Alert(
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        name=payload.name,
        metric=payload.metric,
        comparator=payload.comparator,
        threshold=payload.threshold,
        severity=payload.severity,
        notify_emails=[str(email) for email in payload.notify_emails],
        created_by_user_id=context.user_id,
    )
    db.add(alert)
    db.flush()
    return AlertResponse.model_validate(alert)


@router.delete("/alerts/{alert_id}", response_model=Message, summary="Delete an alert")
def delete_alert(alert_id: str, db: Db, context: WriteSecurity) -> Message:
    alert = db.get(Alert, alert_id)
    if alert is None or alert.workspace_id != context.workspace_id:
        raise NotFoundError("alert not found")
    db.delete(alert)
    return Message(message="Alert deleted.")


# -------------------------------------------------------------------- feedback


@router.post(
    "/feedback",
    response_model=Message,
    status_code=status.HTTP_201_CREATED,
    summary="Submit structured product feedback",
)
def submit_feedback(payload: FeedbackRequest, db: Db, context: ReadWorkspace) -> Message:
    db.add(
        FeedbackEntry(
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            user_id=context.user_id,
            **payload.model_dump(),
        )
    )
    db.flush()
    return Message(message="Thank you — your feedback was recorded.")


# ----------------------------------------------------------------------- admin


@router.get("/admin/overview", summary="Platform-wide administrator view")
def admin_overview(
    db: Db,
    _admin: Annotated[CurrentPrincipal, Depends(require_platform_admin)],
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    return dashboard_service.admin_overview(db, days=days)


@router.get("/admin/configuration", summary="Deployment configuration review")
def admin_configuration(
    _admin: Annotated[CurrentPrincipal, Depends(require_platform_admin)],
) -> dict[str, Any]:
    """Reports configuration problems without ever echoing a secret value."""
    settings = get_settings()
    return {
        "environment": settings.environment,
        "job_backend": settings.job_backend,
        "credentials_configured": settings.provider_status_summary(),
        "insecure_defaults": settings.insecure_defaults(),
        "data_training_policy": (
            "Customer data is isolated and is not used for model training unless explicitly "
            "authorized."
        ),
        "checked_at": datetime.now(UTC).isoformat(),
    }
