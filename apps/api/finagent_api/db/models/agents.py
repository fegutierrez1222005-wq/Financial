"""Agent definition tables.

``agent_versions`` and ``agent_prompts`` rows are immutable: editing an agent creates a new
version. Every research run points at a version, which is what makes a run reproducible and
an A/B comparison meaningful.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from finagent_api.db.base import (
    Base,
    EnumString,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
    WorkspaceScopedMixin,
)
from finagent_api.db.types import GUID, JSONB


class Agent(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, SoftDeleteMixin, Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_agent_name_per_workspace"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    archetype: Mapped[str] = mapped_column(EnumString, default="analyst", nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(GUID())
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)


class AgentPrompt(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """Versioned system instructions."""

    __tablename__ = "agent_prompts"
    __table_args__ = (UniqueConstraint("agent_id", "version_number", name="uq_prompt_version_per_agent"),)

    agent_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str | None] = mapped_column(GUID())


class AgentVersion(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """Immutable snapshot of an agent's full configuration."""

    __tablename__ = "agent_versions"
    __table_args__ = (UniqueConstraint("agent_id", "version_number", name="uq_agent_version_number"),)

    agent_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_version_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("agent_prompts.id", ondelete="SET NULL"), index=True
    )
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)
    max_steps: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    output_format: Mapped[str] = mapped_column(EnumString, default="markdown", nullable=False)
    risk_constraints: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    evaluation_suite_keys: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    change_note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str | None] = mapped_column(GUID())
    #: Hash over model + prompt + tools + datasets, used to detect no-op edits.
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class AgentTool(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """A tool enabled for one agent version, with its permissions."""

    __tablename__ = "agent_tools"
    __table_args__ = (UniqueConstraint("agent_version_id", "tool_name", name="uq_agent_version_tool"),)

    agent_version_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    permissions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class AgentModel(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """Model binding for an agent version (separate for future multi-model agents)."""

    __tablename__ = "agent_models"

    agent_version_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_key: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(EnumString, default="primary", nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class AgentDataset(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """Datasets, data sources and documents bound to an agent version."""

    __tablename__ = "agent_datasets"

    agent_version_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    data_source_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    document_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    binding_kind: Mapped[str] = mapped_column(EnumString, default="dataset", nullable=False)
