"""Experiment tracking, model catalog and benchmarking tables."""

from __future__ import annotations

from datetime import datetime

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
from finagent_api.db.types import GUID, JSONB, UTCDateTime


class Experiment(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, SoftDeleteMixin, Base):
    """A controlled comparison: vary one factor (agent, model or prompt) at a time."""

    __tablename__ = "experiments"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    #: What is being varied: agent_version | model | prompt_version | tools
    variable: Mapped[str] = mapped_column(EnumString, default="model", nullable=False)
    suite_key: Mapped[str | None] = mapped_column(String(120), index=True)
    task_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    configuration: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(EnumString, default="QUEUED", nullable=False, index=True)
    conclusion: Mapped[str | None] = mapped_column(Text)
    results_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_by_user_id: Mapped[str | None] = mapped_column(GUID())


class ExperimentRun(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """One cell of an experiment matrix."""

    __tablename__ = "experiment_runs"

    experiment_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    arm_label: Mapped[str] = mapped_column(String(200), nullable=False)
    agent_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    agent_version_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    prompt_version_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    model: Mapped[str | None] = mapped_column(String(120), index=True)
    suite_key: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(EnumString, default="QUEUED", nullable=False, index=True)
    research_run_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    evaluation_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    overall_score: Mapped[float | None] = mapped_column(Float)
    pass_rate: Mapped[float | None] = mapped_column(Float)
    dimension_scores: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mean_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hallucination_rate: Mapped[float | None] = mapped_column(Float)
    citation_coverage: Mapped[float | None] = mapped_column(Float)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)


class ModelCatalogEntry(UUIDMixin, TimestampMixin, Base):
    """Platform-wide model catalog with availability and estimated pricing."""

    __tablename__ = "models"
    __table_args__ = (UniqueConstraint("key", name="uq_model_key"),)

    key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    context_window: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_cost_per_1k: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    output_cost_per_1k: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    supports_tools: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class Benchmark(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, SoftDeleteMixin, Base):
    """A saved agent comparison over a suite of tasks."""

    __tablename__ = "benchmarks"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    suite_key: Mapped[str | None] = mapped_column(String(120), index=True)
    agent_version_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(EnumString, default="QUEUED", nullable=False, index=True)
    ranking_weights: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_by_user_id: Mapped[str | None] = mapped_column(GUID())


class BenchmarkEntry(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "benchmark_entries"

    benchmark_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("benchmarks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    agent_version_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    agent_name: Mapped[str | None] = mapped_column(String(200))
    model: Mapped[str | None] = mapped_column(String(120))
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overall_score: Mapped[float | None] = mapped_column(Float)
    dimension_scores: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    pass_rate: Mapped[float | None] = mapped_column(Float)
    hallucination_rate: Mapped[float | None] = mapped_column(Float)
    citation_coverage: Mapped[float | None] = mapped_column(Float)
    mean_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    research_efficiency: Mapped[float | None] = mapped_column(Float)
    evaluation_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
