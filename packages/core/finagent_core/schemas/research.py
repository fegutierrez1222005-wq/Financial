"""Research execution contracts shared by the runner, the evaluators and the API."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from finagent_core.schemas.enums import (
    ClaimSupport,
    OutputFormat,
    ResearchStepKind,
    RunStatus,
    TaskTemplate,
)
from finagent_core.schemas.thesis import InvestmentThesis


def _now() -> datetime:
    return datetime.now(UTC)


class TaskSpec(BaseModel):
    """What the agent is asked to do, including its information cutoff."""

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    template: TaskTemplate = TaskTemplate.CUSTOM
    title: str
    question: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    output_format: OutputFormat = OutputFormat.MARKDOWN
    information_cutoff: datetime | None = None
    required_output_fields: list[str] = Field(default_factory=list)

    def prompt_payload(self) -> dict[str, Any]:
        """The JSON block handed to the model as the task definition."""
        return {
            "task_id": self.id,
            "template": self.template,
            "title": self.title,
            "question": self.question,
            "output_format": self.output_format,
            "required_output_fields": self.required_output_fields,
            "information_cutoff": (
                self.information_cutoff.isoformat() if self.information_cutoff else None
            ),
            **self.inputs,
        }


class EvidenceItem(BaseModel):
    """A retrieved chunk shown to the agent. The unit of citation."""

    chunk_id: str
    document_id: str | None = None
    document_name: str | None = None
    page_number: int | None = None
    text: str
    similarity: float = 0.0
    publication_timestamp: datetime | None = None
    source: str | None = None
    is_demo: bool = False


class ToolCallRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    status: str = "SUCCEEDED"
    error_code: str | None = None
    error_message: str | None = None
    latency_ms: int = 0
    started_at: datetime = Field(default_factory=_now)


class TraceStep(BaseModel):
    """One recorded agent action. The trace is the audit trail of the research."""

    model_config = ConfigDict(use_enum_values=True)

    sequence: int
    kind: ResearchStepKind
    action: str
    input: Any = None
    output: Any = None
    tool_name: str | None = None
    model: str | None = None
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime = Field(default_factory=_now)


class UsageSummary(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    model_calls: int = 0
    tool_calls: int = 0
    python_seconds: float = 0.0
    data_api_calls: int = 0
    estimated_cost_usd: float = 0.0
    duration_ms: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class Claim(BaseModel):
    """An atomic factual assertion extracted from agent output."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    numeric_value: float | None = None
    unit: str | None = None
    cited_chunk_ids: list[str] = Field(default_factory=list)
    support_level: ClaimSupport = ClaimSupport.UNKNOWN
    matched_chunk_id: str | None = None
    evidence_quote: str | None = None
    similarity: float = 0.0
    explanation: str | None = None
    is_forward_looking: bool = False


class CitationRecord(BaseModel):
    claim_id: str
    claim_text: str
    chunk_id: str
    document_id: str | None = None
    document_name: str | None = None
    page_number: int | None = None
    quote: str | None = None
    support_level: ClaimSupport = ClaimSupport.UNKNOWN
    similarity: float = 0.0


class AgentRunSpec(BaseModel):
    """Immutable description of *how* a run executed — the reproducibility record."""

    model_config = ConfigDict(use_enum_values=True)

    agent_id: str
    agent_version_id: str
    agent_name: str
    version_number: int = 1
    model: str = "mock-analyst-v1"
    temperature: float = 0.2
    max_tokens: int = 2048
    max_steps: int = 8
    timeout_seconds: int = 300
    system_prompt: str = ""
    prompt_version_id: str | None = None
    prompt_version_number: int = 1
    tools: list[str] = Field(default_factory=list)
    dataset_ids: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    output_format: OutputFormat = OutputFormat.MARKDOWN
    risk_constraints: dict[str, Any] = Field(default_factory=dict)
    information_cutoff: datetime | None = None

    def reproducibility_key(self) -> str:
        """Stable hash of everything that determines the run's behaviour."""
        payload = {
            "agent_version_id": self.agent_version_id,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "max_steps": self.max_steps,
            "prompt_version_id": self.prompt_version_id,
            "system_prompt_sha256": hashlib.sha256(self.system_prompt.encode()).hexdigest(),
            "tools": sorted(self.tools),
            "dataset_ids": sorted(self.dataset_ids),
            "document_ids": sorted(self.document_ids),
            "output_format": self.output_format,
            "information_cutoff": (
                self.information_cutoff.isoformat() if self.information_cutoff else None
            ),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class RunResult(BaseModel):
    """Everything produced by one agent run — the input to evaluation."""

    model_config = ConfigDict(use_enum_values=True)

    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: RunStatus = RunStatus.SUCCEEDED
    spec: AgentRunSpec | None = None
    task: TaskSpec | None = None
    output_text: str = ""
    thesis: InvestmentThesis | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    usage: UsageSummary = Field(default_factory=UsageSummary)
    confidence: float | None = None
    error_code: str | None = None
    error_message: str | None = None
    warnings: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
    used_mock_model: bool = False
    information_cutoff: datetime | None = None

    @property
    def evidence_by_id(self) -> dict[str, EvidenceItem]:
        return {item.chunk_id: item for item in self.evidence}

    @property
    def tool_names(self) -> list[str]:
        return [call.tool_name for call in self.tool_calls]

    @property
    def failed_tool_calls(self) -> list[ToolCallRecord]:
        return [call for call in self.tool_calls if call.status != "SUCCEEDED"]
