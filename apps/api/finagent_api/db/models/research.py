"""Research task, run and trace tables. The trace is the audit trail of the research."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from finagent_api.db.base import Base, EnumString, TimestampMixin, UUIDMixin, WorkspaceScopedMixin
from finagent_api.db.types import GUID, JSONB, UTCDateTime


class ResearchTask(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "research_tasks"

    template_key: Mapped[str] = mapped_column(EnumString, default="custom", nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    required_output_fields: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    output_format: Mapped[str] = mapped_column(EnumString, default="markdown", nullable=False)
    information_cutoff: Mapped[datetime | None] = mapped_column(UTCDateTime())
    evaluation_case_key: Mapped[str | None] = mapped_column(String(120), index=True)
    evaluation_suite_key: Mapped[str | None] = mapped_column(String(120), index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(GUID())


class ResearchRun(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "research_runs"

    task_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_version_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt_version_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    experiment_run_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    parent_run_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    debate_role: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(EnumString, default="QUEUED", nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    python_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    data_api_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    output_text: Mapped[str | None] = mapped_column(Text)
    thesis: Mapped[dict | None] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Float)
    citation_coverage: Mapped[float | None] = mapped_column(Float)
    hallucination_rate: Mapped[float | None] = mapped_column(Float)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    information_cutoff: Mapped[datetime | None] = mapped_column(UTCDateTime())
    used_mock_model: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    warnings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    #: Hash of everything that determines behaviour; identical keys should reproduce.
    reproducibility_key: Mapped[str | None] = mapped_column(String(64), index=True)
    reproduced_from_run_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    dataset_snapshot_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    document_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    triggered_by_user_id: Mapped[str | None] = mapped_column(GUID())
    triggered_by_api_key_id: Mapped[str | None] = mapped_column(GUID())


class ResearchStep(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """High-level plan steps (distinct from the low-level trace)."""

    __tablename__ = "research_steps"

    run_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(EnumString, default="plan", nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(EnumString, default="SUCCEEDED", nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class AgentTrace(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "agent_traces"

    run_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AgentTraceStep(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "agent_trace_steps"

    trace_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("agent_traces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(GUID(), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(EnumString, nullable=False)
    action: Mapped[str] = mapped_column(String(400), nullable=False)
    input_json: Mapped[dict | None] = mapped_column(JSONB)
    output_json: Mapped[dict | None] = mapped_column(JSONB)
    tool_name: Mapped[str | None] = mapped_column(String(64), index=True)
    model: Mapped[str | None] = mapped_column(String(120))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class AgentMessage(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "agent_messages"

    run_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(EnumString, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(String(64))
    tool_call_id: Mapped[str | None] = mapped_column(String(64))
    token_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ToolCall(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "tool_calls"

    run_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    arguments: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(EnumString, default="SUCCEEDED", nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)


class ModelRun(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """One provider call. The unit of cost and latency observability."""

    __tablename__ = "model_runs"

    run_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    evaluation_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(EnumString, default="research", nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(120))
    finish_reason: Mapped[str | None] = mapped_column(String(64))
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))


class RunEvidence(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """Exactly what the agent was shown during a run.

    Persisted verbatim because citation verification must compare claims against the
    evidence available *at run time*, not whatever the index contains later.
    """

    __tablename__ = "run_evidence"

    run_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_ref: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    chunk_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    document_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    document_name: Mapped[str | None] = mapped_column(String(300))
    page_number: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    similarity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    publication_timestamp: Mapped[datetime | None] = mapped_column(UTCDateTime())
    source: Mapped[str | None] = mapped_column(String(120))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Claim(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    """An extracted claim with its verification verdict."""

    __tablename__ = "claims"

    run_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evaluation_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(EnumString, default="FACTUAL", nullable=False)
    section: Mapped[str | None] = mapped_column(String(120))
    numeric_value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32))
    support_level: Mapped[str] = mapped_column(EnumString, default="UNKNOWN", nullable=False, index=True)
    cited_chunk_refs: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    matched_chunk_ref: Mapped[str | None] = mapped_column(String(200))
    evidence_quote: Mapped[str | None] = mapped_column(Text)
    similarity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
