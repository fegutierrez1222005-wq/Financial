"""Identity, tenancy and credential tables."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from finagent_api.db.base import (
    Base,
    EnumString,
    OrganizationScopedMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)
from finagent_api.db.types import GUID, JSONB, UTCDateTime


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: TOTP secret, encrypted at rest. Never returned by any endpoint.
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    mfa_confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    onboarding_state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    plan: Mapped[str] = mapped_column(EnumString, default="trial", nullable=False)
    #: Customer data is never used for model training unless explicitly authorised.
    data_training_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sso_enforced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sso_provider: Mapped[str | None] = mapped_column(String(64))
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class OrganizationMember(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member"),)

    organization_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(EnumString, default="RESEARCHER", nullable=False)


class Workspace(UUIDMixin, TimestampMixin, SoftDeleteMixin, OrganizationScopedMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_workspace_slug"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    use_case: Mapped[str | None] = mapped_column(String(120))
    #: Default information cutoff applied to research runs created in this workspace.
    default_information_cutoff: Mapped[datetime | None] = mapped_column(UTCDateTime())
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class WorkspaceMember(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),)

    workspace_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(EnumString, default="RESEARCHER", nullable=False)
    invited_by_user_id: Mapped[str | None] = mapped_column(GUID())


class Invitation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "invitations"

    organization_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[str] = mapped_column(EnumString, default="RESEARCHER", nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    invited_by_user_id: Mapped[str | None] = mapped_column(GUID())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Session(UUIDMixin, TimestampMixin, Base):
    """Refresh-token session. Access tokens are stateless; refresh tokens are revocable."""

    __tablename__ = "sessions"

    user_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    mfa_satisfied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class OAuthIdentity(UUIDMixin, TimestampMixin, Base):
    """Link to an external identity provider (adapter seam for SSO)."""

    __tablename__ = "oauth_identities"
    __table_args__ = (UniqueConstraint("provider", "provider_subject", name="uq_oauth_subject"),)

    user_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    raw_profile: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class ApiKey(UUIDMixin, TimestampMixin, Base):
    """Programmatic credential. Only a hash is stored; the secret is shown once."""

    __tablename__ = "api_keys"

    organization_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[str | None] = mapped_column(GUID())
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    scopes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    role: Mapped[str] = mapped_column(EnumString, default="RESEARCHER", nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
