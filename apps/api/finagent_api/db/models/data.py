"""Data source, dataset, document and citation tables."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from finagent_api.db.base import (
    Base,
    EnumString,
    OrganizationScopedMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
    WorkspaceScopedMixin,
)
from finagent_api.db.types import GUID, JSONB, UTCDateTime, Vector

EMBEDDING_DIM = 1536


class DataSource(UUIDMixin, TimestampMixin, OrganizationScopedMixin, Base):
    """A configured provider instance (SEC EDGAR, Polygon, demo, uploaded file...)."""

    __tablename__ = "data_sources"

    workspace_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(EnumString, default="market_data", nullable=False)
    status: Mapped[str] = mapped_column(EnumString, default="unavailable", nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    capabilities: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_error: Mapped[str | None] = mapped_column(Text)


class DataConnector(UUIDMixin, TimestampMixin, OrganizationScopedMixin, Base):
    """Credential metadata for a data source. Secrets are encrypted, never returned."""

    __tablename__ = "data_connectors"

    data_source_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    secret_encrypted: Mapped[str | None] = mapped_column(Text)
    secret_last_four: Mapped[str | None] = mapped_column(String(8))
    rotated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_by_user_id: Mapped[str | None] = mapped_column(GUID())


class DataPermission(UUIDMixin, TimestampMixin, OrganizationScopedMixin, Base):
    """Grants a workspace/role access to a data source."""

    __tablename__ = "data_permissions"
    __table_args__ = (
        UniqueConstraint("data_source_id", "workspace_id", "role", name="uq_data_permission"),
    )

    data_source_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(EnumString, default="RESEARCHER", nullable=False)
    can_read: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Dataset(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, SoftDeleteMixin, Base):
    __tablename__ = "datasets"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(EnumString, default="table", nullable=False)
    source: Mapped[str] = mapped_column(String(120), default="upload", nullable=False)
    data_source_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    document_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    schema_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coverage_start: Mapped[date | None] = mapped_column(Date)
    coverage_end: Mapped[date | None] = mapped_column(Date)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    quality_report: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_snapshot_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(GUID())


class DatasetSnapshot(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """Content-addressed dataset version, so a run can be reproduced on identical data."""

    __tablename__ = "dataset_snapshots"

    dataset_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    as_of: Mapped[datetime | None] = mapped_column(UTCDateTime())
    storage_uri: Mapped[str | None] = mapped_column(String(500))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class Document(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, SoftDeleteMixin, Base):
    __tablename__ = "documents"

    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    title: Mapped[str | None] = mapped_column(String(400))
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    extension: Mapped[str] = mapped_column(String(16), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(EnumString, default="UPLOADED", nullable=False, index=True)
    #: When this document's content became public. Required for historical (as-of) runs.
    publication_timestamp: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    source_label: Mapped[str | None] = mapped_column(String(300))
    document_type: Mapped[str | None] = mapped_column(String(64))
    ticker: Mapped[str | None] = mapped_column(String(32), index=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    embedding_provider: Mapped[str | None] = mapped_column(String(64))
    embedding_is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    malware_scan_status: Mapped[str] = mapped_column(EnumString, default="not_scanned", nullable=False)
    storage_uri: Mapped[str | None] = mapped_column(String(500))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    warnings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    uploaded_by_user_id: Mapped[str | None] = mapped_column(GUID())


class DocumentChunk(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),)

    document_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    publication_timestamp: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    source_label: Mapped[str | None] = mapped_column(String(300))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    embedding: Mapped[list | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class Citation(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """A claim → chunk link produced by the verification pipeline."""

    __tablename__ = "citations"

    run_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    external_chunk_ref: Mapped[str | None] = mapped_column(String(200))
    document_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    document_name: Mapped[str | None] = mapped_column(String(300))
    page_number: Mapped[int | None] = mapped_column(Integer)
    quote: Mapped[str | None] = mapped_column(Text)
    support_level: Mapped[str] = mapped_column(EnumString, default="UNKNOWN", nullable=False)
    similarity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
