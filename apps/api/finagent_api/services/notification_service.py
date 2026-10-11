"""Notifications, webhooks and alerts.

Webhook deliveries are persisted before dispatch and signed with HMAC-SHA256, so a receiver
can verify authenticity and the platform can retry without duplicating side effects. Email
delivery sits behind an :class:`EmailSender` seam; the default sender records the
notification and reports that no transport is configured rather than pretending mail was
sent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from finagent_api.db.models import Alert, Notification, Webhook, WebhookDelivery
from finagent_api.security.crypto import decrypt_secret, sign_payload
from finagent_core.logging import get_logger

logger = get_logger(__name__)

WEBHOOK_EVENTS = (
    "research.completed",
    "research.failed",
    "evaluation.completed",
    "backtest.completed",
    "benchmark.completed",
    "agent.failed",
    "alert.fired",
)
MAX_ATTEMPTS = 5


class EmailSender(Protocol):
    key: str

    def send(self, *, to: str, subject: str, body: str) -> tuple[bool, str]: ...


@dataclass
class UnconfiguredEmailSender:
    """Default sender: records the intent and states plainly that mail is not configured."""

    key: str = "unconfigured"

    def send(self, *, to: str, subject: str, body: str) -> tuple[bool, str]:
        return False, "No email transport is configured; the notification is available in-app only."


_email_sender: EmailSender = UnconfiguredEmailSender()


def set_email_sender(sender: EmailSender) -> None:
    global _email_sender
    _email_sender = sender


def notify(
    db: DbSession,
    *,
    organization_id: str,
    event_type: str,
    title: str,
    body: str | None = None,
    workspace_id: str | None = None,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    severity: str = "INFO",
    email_to: str | None = None,
) -> Notification:
    notification = Notification(
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        channel="email" if email_to else "in_app",
        event_type=event_type,
        title=title[:300],
        body=body,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        severity=severity,
    )
    if email_to:
        delivered, detail = _email_sender.send(to=email_to, subject=title, body=body or title)
        notification.delivered_at = datetime.now(UTC) if delivered else None
        notification.delivery_error = None if delivered else detail
    else:
        notification.delivered_at = datetime.now(UTC)
    db.add(notification)
    db.flush()
    return notification


def list_notifications(
    db: DbSession, *, organization_id: str, user_id: str | None = None, limit: int = 50
) -> list[Notification]:
    query = select(Notification).where(Notification.organization_id == organization_id)
    if user_id:
        query = query.where((Notification.user_id == user_id) | (Notification.user_id.is_(None)))
    return list(db.scalars(query.order_by(Notification.created_at.desc()).limit(limit)))


def mark_read(db: DbSession, *, notification_id: str, organization_id: str) -> Notification | None:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.organization_id != organization_id:
        return None
    notification.read_at = datetime.now(UTC)
    db.flush()
    return notification


def dispatch_event(
    db: DbSession,
    *,
    organization_id: str,
    event_type: str,
    payload: dict[str, Any],
    workspace_id: str | None = None,
    deliver: bool = True,
) -> list[WebhookDelivery]:
    """Queue (and optionally deliver) an event to every subscribed webhook."""
    deliveries: list[WebhookDelivery] = []
    for hook in db.scalars(
        select(Webhook).where(Webhook.organization_id == organization_id, Webhook.is_active.is_(True))
    ):
        if hook.events and event_type not in hook.events:
            continue
        if hook.workspace_id and workspace_id and hook.workspace_id != workspace_id:
            continue
        body = {
            "event": event_type,
            "created_at": datetime.now(UTC).isoformat(),
            "organization_id": organization_id,
            "workspace_id": workspace_id,
            "data": payload,
        }
        raw = json.dumps(body, sort_keys=True, default=str).encode("utf-8")
        secret = decrypt_secret(hook.secret_encrypted) or ""
        delivery = WebhookDelivery(
            organization_id=organization_id,
            webhook_id=hook.id,
            event_type=event_type,
            payload=body,
            signature=sign_payload(raw, secret) if secret else None,
            status="QUEUED",
        )
        db.add(delivery)
        db.flush()
        deliveries.append(delivery)
        if deliver:
            attempt_delivery(db, delivery_id=delivery.id)
    return deliveries


def attempt_delivery(db: DbSession, *, delivery_id: str) -> WebhookDelivery:
    delivery = db.get(WebhookDelivery, delivery_id)
    if delivery is None:
        raise ValueError("delivery not found")
    hook = db.get(Webhook, delivery.webhook_id)
    if hook is None or not hook.is_active:
        delivery.status = "CANCELLED"
        db.flush()
        return delivery

    delivery.attempt_count += 1
    raw = json.dumps(delivery.payload, sort_keys=True, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "finagent-lab-webhooks/1",
        "X-Finagent-Event": delivery.event_type,
        "X-Finagent-Delivery": delivery.id,
    }
    if delivery.signature:
        headers["X-Finagent-Signature"] = f"sha256={delivery.signature}"

    try:
        response = httpx.post(hook.url, content=raw, headers=headers, timeout=10.0)
        delivery.response_status = response.status_code
        delivery.response_body = response.text[:2000]
        if 200 <= response.status_code < 300:
            delivery.status = "DELIVERED"
            delivery.delivered_at = datetime.now(UTC)
            hook.failure_count = 0
            hook.last_delivery_at = delivery.delivered_at
        else:
            _schedule_retry(delivery, hook)
    except httpx.HTTPError as exc:
        delivery.error_message = str(exc)[:500]
        _schedule_retry(delivery, hook)
    db.flush()
    logger.info(
        "webhook_delivery",
        extra={
            "webhook_id": hook.id,
            "event": delivery.event_type,
            "status": delivery.status,
            "attempt": delivery.attempt_count,
        },
    )
    return delivery


def _schedule_retry(delivery: WebhookDelivery, hook: Webhook) -> None:
    hook.failure_count += 1
    if delivery.attempt_count >= MAX_ATTEMPTS:
        delivery.status = "FAILED"
        if hook.failure_count >= 20:
            hook.is_active = False
        return
    delivery.status = "RETRY"
    delivery.next_attempt_at = datetime.now(UTC) + timedelta(
        seconds=min(2**delivery.attempt_count, 3600)
    )


def evaluate_alerts(
    db: DbSession, *, organization_id: str, workspace_id: str | None, metrics: dict[str, float]
) -> list[Alert]:
    """Fire any alert whose threshold the supplied metrics breach."""
    fired: list[Alert] = []
    for alert in db.scalars(
        select(Alert).where(Alert.organization_id == organization_id, Alert.is_enabled.is_(True))
    ):
        if alert.workspace_id and workspace_id and alert.workspace_id != workspace_id:
            continue
        value = metrics.get(alert.metric)
        if value is None:
            continue
        breached = value > alert.threshold if alert.comparator == ">" else value < alert.threshold
        if not breached:
            continue
        alert.last_fired_at = datetime.now(UTC)
        alert.last_value = value
        fired.append(alert)
        notify(
            db,
            organization_id=organization_id,
            workspace_id=workspace_id,
            event_type="alert.fired",
            title=f"Alert: {alert.name}",
            body=(
                f"{alert.metric} is {value:.4g}, which breaches the configured threshold of "
                f"{alert.threshold:.4g}."
            ),
            severity=alert.severity,
            resource_type="alert",
            resource_id=alert.id,
        )
        dispatch_event(
            db,
            organization_id=organization_id,
            workspace_id=workspace_id,
            event_type="alert.fired",
            payload={
                "alert": alert.name,
                "metric": alert.metric,
                "value": value,
                "threshold": alert.threshold,
            },
        )
    db.flush()
    return fired
