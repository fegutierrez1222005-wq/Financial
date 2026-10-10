"""Platform tables: audit, alerts, notifications, webhooks, billing, usage, feedback."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from finagent_api.db.base import Base, EnumString, OrganizationScopedMixin, TimestampMixin, UUIDMixin
from finagent_api.db.types import GUID, JSONB, UTCDateTime


class AuditLog(UUIDMixin, TimestampMixin, OrganizationScopedMixin, Base):
    """Append-only record of security- and research-relevant actions."""

    __tablename__ = "audit_logs"

    workspace_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    user_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    api_key_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), index=True)
    outcome: Mapped[str] = mapped_column(EnumString, default="SUCCESS", nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class Alert(UUIDMixin, TimestampMixin, OrganizationScopedMixin, Base):
    __tablename__ = "alerts"

    workspace_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    #: hallucination_rate | overall_score | cost_usd | evaluation_failures
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    comparator: Mapped[str] = mapped_column(String(8), default=">", nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(EnumString, default="WARNING", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_fired_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_value: Mapped[float | None] = mapped_column(Float)
    notify_emails: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(GUID())


class Notification(UUIDMixin, TimestampMixin, OrganizationScopedMixin, Base):
    __tablename__ = "notifications"

    workspace_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    user_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    channel: Mapped[str] = mapped_column(EnumString, default="in_app", nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(EnumString, default="INFO", nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    delivered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    delivery_error: Mapped[str | None] = mapped_column(Text)


class Webhook(UUIDMixin, TimestampMixin, OrganizationScopedMixin, Base):
    __tablename__ = "webhooks"

    workspace_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    events: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    secret_encrypted: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_delivery_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_by_user_id: Mapped[str | None] = mapped_column(GUID())


class WebhookDelivery(UUIDMixin, TimestampMixin, OrganizationScopedMixin, Base):
    __tablename__ = "webhook_deliveries"

    webhook_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    signature: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(EnumString, default="QUEUED", nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    next_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Subscription(UUIDMixin, TimestampMixin, OrganizationScopedMixin, Base):
    """Plan and entitlements. No payment processor is wired in the MVP."""

    __tablename__ = "subscriptions"

    plan: Mapped[str] = mapped_column(EnumString, default="trial", nullable=False)
    status: Mapped[str] = mapped_column(EnumString, default="active", nullable=False)
    seats: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    research_run_limit: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    evaluation_limit: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    backtest_limit: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    document_page_limit: Mapped[int] = mapped_column(Integer, default=5000, nullable=False)
    monthly_cost_cap_usd: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    trial_ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    current_period_start: Mapped[datetime | None] = mapped_column(UTCDateTime())
    current_period_end: Mapped[datetime | None] = mapped_column(UTCDateTime())
    features: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    external_customer_ref: Mapped[str | None] = mapped_column(String(120))


class UsageEvent(UUIDMixin, TimestampMixin, OrganizationScopedMixin, Base):
    """Metered unit of consumption. The basis of cost observability and billing."""

    __tablename__ = "usage_events"

    workspace_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    user_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    kind: Mapped[str] = mapped_column(EnumString, nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="count", nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_estimated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    run_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    evaluation_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    backtest_run_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    model: Mapped[str | None] = mapped_column(String(120))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class RateLimitEvent(UUIDMixin, TimestampMixin, Base):
    """Denied requests, surfaced in the admin security view."""

    __tablename__ = "rate_limit_events"

    organization_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    user_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    api_key_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(String(300), nullable=False)
    limit_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64))


class FeedbackEntry(UUIDMixin, TimestampMixin, OrganizationScopedMixin, Base):
    """Customer-validation module: which workflow saves time and is worth paying for."""

    __tablename__ = "feedback_entries"

    workspace_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    user_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    research_problem: Mapped[str] = mapped_column(Text, nullable=False)
    current_workflow: Mapped[str | None] = mapped_column(Text)
    manual_minutes: Mapped[int | None] = mapped_column(Integer)
    ai_minutes: Mapped[int | None] = mapped_column(Integer)
    errors_observed: Mapped[str | None] = mapped_column(Text)
    willingness_to_pay_usd: Mapped[float | None] = mapped_column(Float)
    would_recommend: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)
