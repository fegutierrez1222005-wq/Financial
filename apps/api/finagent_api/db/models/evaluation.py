"""Evaluation suite, case, run, result and score tables."""

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


class EvaluationSuite(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, SoftDeleteMixin, Base):
    __tablename__ = "evaluation_suites"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_suite_key_per_workspace"),)

    key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    weights: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dataset_note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str | None] = mapped_column(GUID())


class EvaluationCase(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "evaluation_cases"
    __table_args__ = (UniqueConstraint("suite_id", "key", name="uq_case_key_per_suite"),)

    suite_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("evaluation_suites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    expected_value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32))
    acceptable_low: Mapped[float | None] = mapped_column(Float)
    acceptable_high: Mapped[float | None] = mapped_column(Float)
    required_sources: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    forbidden_sources: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    required_fields: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    difficulty: Mapped[str] = mapped_column(EnumString, default="medium", nullable=False)
    category: Mapped[str] = mapped_column(EnumString, default="financial_statements", nullable=False)
    evaluation_method: Mapped[str] = mapped_column(
        EnumString, default="deterministic_numeric", nullable=False
    )
    information_cutoff: Mapped[datetime | None] = mapped_column(UTCDateTime())
    inputs: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class Evaluation(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """One evaluation job: either a single run's quality, or a whole suite."""

    __tablename__ = "evaluations"

    kind: Mapped[str] = mapped_column(EnumString, default="run", nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("research_runs.id", ondelete="CASCADE"), index=True
    )
    suite_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    suite_key: Mapped[str | None] = mapped_column(String(120), index=True)
    agent_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    agent_version_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    experiment_run_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    status: Mapped[str] = mapped_column(EnumString, default="QUEUED", nullable=False, index=True)
    overall_score: Mapped[float | None] = mapped_column(Float)
    pass_rate: Mapped[float | None] = mapped_column(Float)
    case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hallucination_rate: Mapped[float | None] = mapped_column(Float)
    citation_coverage: Mapped[float | None] = mapped_column(Float)
    judge_model: Mapped[str | None] = mapped_column(String(120))
    judge_is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    weights: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    warnings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    triggered_by_user_id: Mapped[str | None] = mapped_column(GUID())


class EvaluationResult(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """Per-case outcome, including why it failed."""

    __tablename__ = "evaluation_results"

    evaluation_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    case_key: Mapped[str | None] = mapped_column(String(120), index=True)
    run_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[float | None] = mapped_column(Float)
    expected: Mapped[str | None] = mapped_column(Text)
    actual: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(String(64), index=True)
    failure_title: Mapped[str | None] = mapped_column(String(300))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(EnumString, default="WARNING", nullable=False)
    dimension: Mapped[str | None] = mapped_column(EnumString)
    evaluator: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str | None] = mapped_column(String(300))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class EvaluationScore(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """Per-dimension score with the weight actually applied."""

    __tablename__ = "evaluation_scores"
    __table_args__ = (UniqueConstraint("evaluation_id", "dimension", name="uq_evaluation_dimension"),)

    evaluation_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension: Mapped[str] = mapped_column(EnumString, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
