"""Declarative base and shared mixins."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from finagent_api.db.types import GUID, UTCDateTime, new_uuid


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, server_default=func.now(), nullable=False
    )


class UUIDMixin:
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)


class SoftDeleteMixin:
    """Content deletions are soft so audit trails and traces survive.

    Retrieval paths must filter ``deleted_at IS NULL``; asserted by
    ``tests/security/test_critical_controls.py``.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class OrganizationScopedMixin:
    """Every tenant-visible row carries its organization."""

    @declared_attr
    def organization_id(cls) -> Mapped[str]:
        return mapped_column(
            GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
        )


class WorkspaceScopedMixin(OrganizationScopedMixin):
    @declared_attr
    def workspace_id(cls) -> Mapped[str]:
        return mapped_column(
            GUID(), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
        )


#: Enumerations are stored as strings; see docs/DATABASE.md for the rationale.
EnumString = String(64)
