"""Request and response models.

These types are the API contract. Two rules matter more than the rest:

* Nothing here exposes a secret. Provider credentials, password hashes, API key hashes,
  MFA secrets and webhook signing secrets have no field on any response model. The plaintext
  of a newly created API key is the single exception and is returned exactly once.
* Anything produced by a mock provider or demo dataset carries an explicit flag, so a client
  can never render simulated output as if it were live.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from finagent_core.schemas.enums import (
    OutputFormat,
    RebalanceFrequency,
    TaskTemplate,
    WorkspaceRole,
)

# --------------------------------------------------------------------------- base


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class Message(ApiModel):
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class Page(ApiModel):
    total: int
    limit: int
    offset: int


class JobAccepted(ApiModel):
    """Returned when work was handed to the queue rather than completed in-request."""

    job_name: str
    backend: str
    job_id: str | None = None
    completed: bool
    error: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None


# ------------------------------------------------------------------------ health


class HealthResponse(ApiModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    environment: str


class ReadinessComponent(ApiModel):
    name: str
    ready: bool
    detail: str | None = None


class ReadinessResponse(ApiModel):
    ready: bool
    components: list[ReadinessComponent]


# -------------------------------------------------------------------------- auth


class RegisterRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)
    full_name: str | None = Field(default=None, max_length=200)
    organization_name: str | None = Field(default=None, max_length=200)
    seed_demo_workspace: bool = Field(
        default=True,
        description="Create the clearly-labelled ACME Technologies demo workspace.",
    )


class LoginRequest(ApiModel):
    email: EmailStr
    password: str
    mfa_code: str | None = Field(default=None, max_length=10)


class RefreshRequest(ApiModel):
    refresh_token: str


class TokenResponse(ApiModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user_id: str
    organization_id: str | None = None
    mfa_satisfied: bool = False


class UserResponse(ApiModel):
    id: str
    email: str
    full_name: str | None
    is_active: bool
    is_platform_admin: bool
    mfa_enabled: bool
    last_login_at: datetime | None
    onboarding_state: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SessionResponse(ApiModel):
    id: str
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    ip_address: str | None
    user_agent: str | None
    mfa_satisfied: bool


class ChangePasswordRequest(ApiModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=200)


class MfaEnrolResponse(ApiModel):
    secret: str = Field(description="Shown once during enrolment so the user can store it.")
    provisioning_uri: str
    recovery_codes: list[str]
    note: str


class MfaConfirmRequest(ApiModel):
    code: str = Field(min_length=6, max_length=6)


class MfaDisableRequest(ApiModel):
    password: str


# ------------------------------------------------------------ orgs and workspaces


class OrganizationResponse(ApiModel):
    id: str
    name: str
    slug: str
    plan: str
    data_training_opt_in: bool
    sso_enforced: bool
    created_at: datetime


class WorkspaceCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    use_case: str | None = Field(default=None, max_length=120)
    default_information_cutoff: datetime | None = None


class WorkspaceUpdateRequest(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    use_case: str | None = Field(default=None, max_length=120)
    default_information_cutoff: datetime | None = None


class WorkspaceResponse(ApiModel):
    id: str
    organization_id: str
    name: str
    slug: str
    description: str | None
    use_case: str | None
    default_information_cutoff: datetime | None
    is_demo: bool
    created_at: datetime
    role: str | None = None


class MemberResponse(ApiModel):
    id: str
    user_id: str
    email: str
    full_name: str | None
    role: str
    created_at: datetime


class InviteRequest(ApiModel):
    email: EmailStr
    role: WorkspaceRole = WorkspaceRole.RESEARCHER


class InviteResponse(ApiModel):
    id: str
    email: str
    role: str
    expires_at: datetime
    #: Returned once so the caller can deliver it; never stored in plaintext.
    invitation_token: str
    accept_url: str


class AcceptInviteRequest(ApiModel):
    token: str


class RoleChangeRequest(ApiModel):
    role: WorkspaceRole


class RoleDescription(ApiModel):
    role: str
    rank: int
    permissions: list[str]


# ----------------------------------------------------------------------- api keys


class ApiKeyCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    role: WorkspaceRole = WorkspaceRole.RESEARCHER
    scope_to_workspace: bool = True
    expires_in_days: int | None = Field(default=None, ge=1, le=730)

    @field_validator("role")
    @classmethod
    def _no_privileged_keys(cls, value: WorkspaceRole) -> WorkspaceRole:
        if value in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            raise ValueError("API keys may not hold owner or admin roles")
        return value


class ApiKeyResponse(ApiModel):
    id: str
    name: str
    key_prefix: str
    role: str
    workspace_id: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreatedResponse(ApiKeyResponse):
    #: Shown exactly once. Only a SHA-256 hash is persisted.
    plaintext_key: str
    warning: str = "Store this key now. It cannot be retrieved again."


# ------------------------------------------------------------------------- agents


class AgentCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    instructions: str | None = Field(default=None, max_length=20000)
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=128, le=32000)
    max_steps: int = Field(default=8, ge=1, le=30)
    timeout_seconds: int = Field(default=300, ge=10, le=1800)
    output_format: OutputFormat = OutputFormat.MARKDOWN
    tools: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    dataset_ids: list[str] = Field(default_factory=list)
    data_source_ids: list[str] = Field(default_factory=list)
    evaluation_suite_keys: list[str] = Field(default_factory=list)
    risk_constraints: dict[str, Any] = Field(default_factory=dict)
    archetype: str = Field(default="analyst", max_length=60)
    change_note: str | None = Field(default=None, max_length=500)


class AgentUpdateRequest(AgentCreateRequest):
    """A change always produces a new immutable version, never an in-place edit."""


class AgentVersionResponse(ApiModel):
    id: str
    agent_id: str
    version_number: int
    prompt_version_id: str | None
    model: str
    temperature: float
    max_tokens: int
    max_steps: int
    timeout_seconds: int
    output_format: str
    risk_constraints: dict[str, Any] = Field(default_factory=dict)
    evaluation_suite_keys: list[str] = Field(default_factory=list)
    change_note: str | None
    config_hash: str
    created_at: datetime
    tools: list[str] = Field(default_factory=list)
    bindings: dict[str, list[str]] = Field(default_factory=dict)


class AgentResponse(ApiModel):
    id: str
    workspace_id: str
    name: str
    description: str | None
    archetype: str
    current_version_id: str | None
    is_demo: bool
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    current_version: AgentVersionResponse | None = None
    version_count: int = 0


class PromptVersionResponse(ApiModel):
    id: str
    agent_id: str
    version_number: int
    content: str
    content_hash: str
    label: str | None
    notes: str | None
    created_at: datetime


class ToolDescriptor(ApiModel):
    name: str
    title: str
    description: str
    category: str
    requires_network: bool
    is_deterministic: bool
    available: bool
    unavailable_reason: str | None = None


class ModelDescriptor(ApiModel):
    key: str
    provider: str
    display_name: str
    context_window: int
    input_cost_per_1k: float
    output_cost_per_1k: float
    supports_tools: bool
    available: bool
    is_mock: bool
    notes: str | None = None


# ----------------------------------------------------------------------- research


class TaskCreateRequest(ApiModel):
    template: TaskTemplate = TaskTemplate.CUSTOM
    title: str | None = Field(default=None, max_length=300)
    question: str | None = Field(default=None, max_length=4000)
    inputs: dict[str, Any] = Field(default_factory=dict)
    output_format: OutputFormat | None = None
    information_cutoff: datetime | None = Field(
        default=None,
        description=(
            "Lock the agent to information published at or before this instant. "
            "Evidence with an unknown publication timestamp is excluded."
        ),
    )
    evaluation_case_key: str | None = None
    evaluation_suite_key: str | None = None


class TaskResponse(ApiModel):
    id: str
    workspace_id: str
    template_key: str
    title: str
    question: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    required_output_fields: list[str] = Field(default_factory=list)
    output_format: str
    information_cutoff: datetime | None
    evaluation_case_key: str | None
    evaluation_suite_key: str | None
    created_at: datetime


class TaskTemplateResponse(ApiModel):
    key: str
    name: str
    description: str
    required_inputs: list[str]
    optional_inputs: list[str]
    required_output_fields: list[str]
    recommended_tools: list[str]
    default_output_format: str
    guidance: str | None = None


class RunCreateRequest(ApiModel):
    agent_id: str
    task_id: str | None = None
    task: TaskCreateRequest | None = None
    agent_version_id: str | None = None
    model_override: str | None = None
    run_now: bool = Field(
        default=True, description="Execute immediately; otherwise the run stays queued."
    )

    @field_validator("task_id")
    @classmethod
    def _require_a_task(cls, value: str | None, info) -> str | None:  # noqa: ANN001
        return value


class RunResponse(ApiModel):
    id: str
    workspace_id: str
    task_id: str | None
    agent_id: str
    agent_version_id: str | None
    parent_run_id: str | None
    debate_role: str | None
    model: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    input_tokens: int
    output_tokens: int
    model_calls: int
    tool_call_count: int
    estimated_cost_usd: float
    output_text: str | None
    thesis: dict[str, Any] | None
    confidence: float | None
    citation_coverage: float | None
    hallucination_rate: float | None
    evidence_count: int
    information_cutoff: datetime | None
    used_mock_model: bool
    used_demo_data: bool
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None
    error_message: str | None
    reproducibility_key: str | None
    reproduced_from_run_id: str | None
    created_at: datetime


class TraceStepResponse(ApiModel):
    sequence: int
    kind: str
    action: str | None
    tool_name: str | None
    model: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    input: dict[str, Any] | None = Field(default=None, alias="input_json")
    output: dict[str, Any] | None = Field(default=None, alias="output_json")


class EvidenceResponse(ApiModel):
    chunk_ref: str
    document_id: str | None
    document_name: str | None
    page_number: int | None
    text: str
    similarity: float | None
    publication_timestamp: datetime | None
    source: str | None
    is_demo: bool


class CitationResponse(ApiModel):
    claim_text: str | None
    chunk_ref: str | None = Field(default=None, alias="external_chunk_ref")
    document_id: str | None
    document_name: str | None
    page_number: int | None
    quote: str | None
    support_level: str | None
    similarity: float | None


class RunDetailResponse(ApiModel):
    run: RunResponse
    task: TaskResponse | None
    plan: list[dict[str, Any]] = Field(default_factory=list)
    trace: list[TraceStepResponse] = Field(default_factory=list)
    evidence: list[EvidenceResponse] = Field(default_factory=list)
    citations: list[CitationResponse] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    model_runs: list[dict[str, Any]] = Field(default_factory=list)
    evaluations: list[dict[str, Any]] = Field(default_factory=list)


class DebateRequest(ApiModel):
    roles: list[Literal["bull", "bear", "skeptic", "judge"]] = Field(
        default_factory=lambda: ["bull", "bear", "skeptic", "judge"]
    )


# --------------------------------------------------------------------- evaluation


class EvaluationSuiteResponse(ApiModel):
    id: str
    key: str
    version: str
    name: str
    description: str | None
    weights: dict[str, float] = Field(default_factory=dict)
    is_builtin: bool
    dataset_note: str | None
    case_count: int = 0
    created_at: datetime


class EvaluationCaseResponse(ApiModel):
    id: str
    key: str
    question: str
    expected_answer: str | None
    expected_value: float | None
    unit: str | None
    acceptable_low: float | None
    acceptable_high: float | None
    required_sources: list[str] = Field(default_factory=list)
    forbidden_sources: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    difficulty: str | None
    category: str | None
    evaluation_method: str | None
    information_cutoff: datetime | None
    notes: str | None


class EvaluateRunRequest(ApiModel):
    run_id: str
    weights: dict[str, float] | None = None


class RunSuiteRequest(ApiModel):
    suite_key: str
    agent_id: str
    agent_version_id: str | None = None
    model_override: str | None = None
    max_cases: int | None = Field(default=None, ge=1, le=500)


class EvaluationResponse(ApiModel):
    id: str
    workspace_id: str
    kind: str
    run_id: str | None
    suite_key: str | None
    agent_id: str | None
    agent_version_id: str | None
    status: str
    overall_score: float | None
    pass_rate: float | None
    case_count: int | None
    passed_count: int | None
    hallucination_rate: float | None
    citation_coverage: float | None
    judge_model: str | None
    judge_is_mock: bool
    weights: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    error_code: str | None
    error_message: str | None
    created_at: datetime


class EvaluationDetailResponse(ApiModel):
    evaluation: EvaluationResponse
    scores: list[dict[str, Any]] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    score_interpretation: str


class ScoreboardEntry(ApiModel):
    rank: int
    evaluation_id: str
    agent_id: str
    agent_name: str | None
    agent_version_id: str | None
    version_number: int | None
    model: str | None
    suite_key: str | None
    overall_score: float | None
    pass_rate: float | None
    hallucination_rate: float | None
    citation_coverage: float | None
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    judge_is_mock: bool = False
    evaluated_at: datetime | None = None


# -------------------------------------------------------------------- backtesting


class BacktestCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    universe: list[str] = Field(min_length=1, max_length=50)
    start_date: date
    end_date: date
    strategy_kind: Literal["cross_sectional_momentum", "factor_rank", "equal_weight_buy_hold"] = (
        "cross_sectional_momentum"
    )
    factor: str | None = None
    lookback_days: int = Field(default=126, ge=5, le=1260)
    top_n: int = Field(default=3, ge=1, le=50)
    rebalance_frequency: RebalanceFrequency = RebalanceFrequency.MONTHLY
    transaction_cost_bps: float = Field(default=10.0, ge=0.0, le=500.0)
    slippage_bps: float = Field(default=5.0, ge=0.0, le=500.0)
    initial_capital: float = Field(default=10_000_000.0, gt=0)
    max_position_weight: float = Field(default=0.25, gt=0, le=1.0)
    signal_lag_days: int = Field(
        default=1,
        ge=0,
        le=10,
        description=(
            "Bars between signal observation and execution. Zero means the strategy trades "
            "on the same bar that produced the signal, which is a look-ahead error; the run "
            "is marked invalid."
        ),
    )
    risk_free_rate: float = Field(default=0.02, ge=-0.1, le=0.25)
    benchmark_symbol: str | None = None
    use_splits: bool = True
    information_cutoff: date | None = None
    description: str | None = Field(default=None, max_length=2000)
    origin_run_id: str | None = None

    @field_validator("end_date")
    @classmethod
    def _ordered(cls, value: date, info) -> date:  # noqa: ANN001
        start = info.data.get("start_date")
        if start and value <= start:
            raise ValueError("end_date must be after start_date")
        return value


class BacktestResponse(ApiModel):
    id: str
    workspace_id: str
    name: str
    description: str | None
    universe: list[str]
    strategy: dict[str, Any] = Field(default_factory=dict)
    start_date: date
    end_date: date
    rebalance_frequency: str
    transaction_cost_bps: float
    slippage_bps: float
    initial_capital: float
    max_position_weight: float
    signal_lag_days: int
    risk_free_rate: float
    benchmark_symbol: str | None
    information_cutoff: date | None
    test_split_use_count: int
    spec_fingerprint: str | None
    origin_run_id: str | None
    created_at: datetime


class BacktestSplitResult(ApiModel):
    """One split's result. Splits are reported separately and never averaged."""

    id: str
    split: str
    status: str
    is_valid: bool
    start_date: str | None
    end_date: str | None
    metrics: dict[str, Any] = Field(default_factory=dict)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    rebalance_count: int
    trade_count: int
    is_demo_data: bool
    data_fingerprint: str | None
    equity_curve: list[dict[str, Any]] = Field(default_factory=list)
    trades: list[dict[str, Any]] = Field(default_factory=list)


class BacktestDetailResponse(ApiModel):
    backtest: BacktestResponse
    runs: list[BacktestSplitResult] = Field(default_factory=list)
    overfitting: dict[str, Any] | None = None
    test_split_use_count: int = 0
    reporting_note: str
    disclaimer: str


# -------------------------------------------------------------------- experiments


class ExperimentArmRequest(ApiModel):
    label: str = Field(min_length=1, max_length=80)
    agent_id: str
    agent_version_id: str | None = None
    prompt_version_id: str | None = None
    model: str | None = None


class ExperimentCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    variable: Literal["model", "prompt_version", "agent_version", "tools"] = Field(
        default="model", description="The single thing that differs between arms."
    )
    suite_key: str
    arms: list[ExperimentArmRequest] = Field(min_length=2, max_length=8)
    hypothesis: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=2000)
    max_cases: int | None = Field(default=None, ge=1, le=500)


class ExperimentRunResponse(ApiModel):
    id: str
    arm_label: str
    agent_id: str | None
    agent_version_id: str | None
    model: str | None
    status: str
    overall_score: float | None
    pass_rate: float | None
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    total_cost_usd: float | None
    total_tokens: int | None
    mean_latency_ms: int | None
    hallucination_rate: float | None
    citation_coverage: float | None
    error_code: str | None
    error_message: str | None


class ExperimentResponse(ApiModel):
    id: str
    workspace_id: str
    name: str
    hypothesis: str | None
    description: str | None
    variable: str
    suite_key: str | None
    status: str
    conclusion: str | None
    results_summary: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    arms: list[ExperimentRunResponse] = Field(default_factory=list)


class BenchmarkCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    suite_key: str
    agent_version_ids: list[str] = Field(min_length=1, max_length=20)
    ranking_weights: dict[str, float] | None = None


class BenchmarkEntryResponse(ApiModel):
    agent_id: str | None
    agent_version_id: str | None
    agent_name: str | None
    model: str | None
    rank: int | None
    overall_score: float | None
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    pass_rate: float | None
    hallucination_rate: float | None
    citation_coverage: float | None
    mean_latency_ms: int | None
    total_cost_usd: float | None
    research_efficiency: float | None


class BenchmarkResponse(ApiModel):
    id: str
    name: str
    suite_key: str | None
    status: str
    ranking_weights: dict[str, float] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    entries: list[BenchmarkEntryResponse] = Field(default_factory=list)
    ranking_basis: str


# --------------------------------------------------------------------------- data


class DocumentResponse(ApiModel):
    id: str
    workspace_id: str
    filename: str
    title: str | None
    mime_type: str | None
    extension: str | None
    size_bytes: int
    sha256: str | None
    page_count: int | None
    chunk_count: int
    token_count: int | None
    status: str
    publication_timestamp: datetime | None
    source_label: str | None
    document_type: str | None
    ticker: str | None
    embedding_model: str | None
    embedding_is_mock: bool
    is_demo: bool
    malware_scan_status: str | None
    error_code: str | None
    error_message: str | None
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    deleted_at: datetime | None = None


class DocumentUploadMetadata(ApiModel):
    title: str | None = None
    publication_timestamp: datetime | None = None
    source_label: str | None = None
    document_type: str | None = None
    ticker: str | None = None


class DataSourceResponse(ApiModel):
    id: str
    workspace_id: str | None
    provider_key: str
    name: str
    kind: str
    status: str
    is_demo: bool
    capabilities: list[str] = Field(default_factory=list)
    last_checked_at: datetime | None
    last_error: str | None
    created_at: datetime


class DataSourceCreateRequest(ApiModel):
    provider_key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    #: Written to an encrypted column and never returned by any endpoint.
    credential: str | None = Field(default=None, max_length=500, repr=False)
    config: dict[str, Any] = Field(default_factory=dict)


class DatasetResponse(ApiModel):
    id: str
    name: str
    description: str | None
    kind: str
    source: str | None
    row_count: int | None
    coverage_start: date | None
    coverage_end: date | None
    quality_score: float | None
    quality_report: dict[str, Any] = Field(default_factory=dict)
    is_demo: bool
    created_at: datetime


class ProviderStatusResponse(ApiModel):
    """Provider availability. Never credentials.

    ``credentials_configured`` reports booleans only: whether a key is present, never the
    key. Models backed by the deterministic local provider report ``is_mock=true`` so the
    UI can mark their output as simulated.
    """

    models: list[dict[str, Any]] = Field(default_factory=list)
    available_models: list[dict[str, Any]] = Field(default_factory=list)
    unavailable_models: list[dict[str, Any]] = Field(default_factory=list)
    data_providers: list[dict[str, Any]] = Field(default_factory=list)
    embeddings: list[dict[str, Any]] = Field(default_factory=list)
    credentials_configured: dict[str, bool] = Field(default_factory=dict)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    sandbox: dict[str, Any] = Field(default_factory=dict)
    judge: dict[str, Any] = Field(default_factory=dict)
    notice: str


class SearchRequest(ApiModel):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=6, ge=1, le=25)
    as_of: datetime | None = None
    document_ids: list[str] | None = None


# ----------------------------------------------------------------------- platform


class AuditLogResponse(ApiModel):
    id: str
    action: str
    resource_type: str | None
    resource_id: str | None
    outcome: str
    user_id: str | None
    api_key_id: str | None
    workspace_id: str | None
    ip_address: str | None
    request_id: str | None
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_json")
    created_at: datetime


class WebhookCreateRequest(ApiModel):
    url: str = Field(min_length=8, max_length=2000)
    events: list[str] = Field(min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("url")
    @classmethod
    def _https_only(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("webhook URLs must use https")
        return value


class WebhookResponse(ApiModel):
    id: str
    url: str
    description: str | None
    events: list[str] = Field(default_factory=list)
    is_active: bool
    failure_count: int
    last_delivery_at: datetime | None
    created_at: datetime


class WebhookCreatedResponse(WebhookResponse):
    #: Shown once so the receiver can verify the HMAC signature header.
    signing_secret: str


class NotificationResponse(ApiModel):
    id: str
    event_type: str
    title: str
    body: str | None
    severity: str
    resource_type: str | None
    resource_id: str | None
    read_at: datetime | None
    created_at: datetime


class AlertCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    metric: str = Field(min_length=1, max_length=80)
    comparator: Literal["lt", "lte", "gt", "gte"] = "lt"
    threshold: float
    severity: Literal["INFO", "WARNING", "CRITICAL"] = "WARNING"
    notify_emails: list[EmailStr] = Field(default_factory=list)


class AlertResponse(ApiModel):
    id: str
    name: str
    metric: str
    comparator: str
    threshold: float
    severity: str
    is_enabled: bool
    last_fired_at: datetime | None
    last_value: float | None
    created_at: datetime


class FeedbackRequest(ApiModel):
    research_problem: str = Field(min_length=1, max_length=4000)
    current_workflow: str | None = Field(default=None, max_length=4000)
    manual_minutes: int | None = Field(default=None, ge=0, le=100000)
    ai_minutes: int | None = Field(default=None, ge=0, le=100000)
    errors_observed: str | None = Field(default=None, max_length=4000)
    willingness_to_pay_usd: float | None = Field(default=None, ge=0)
    would_recommend: bool | None = None
    notes: str | None = Field(default=None, max_length=4000)


class SubscriptionResponse(ApiModel):
    plan: str
    status: str
    seats: int
    research_run_limit: int | None
    evaluation_limit: int | None
    backtest_limit: int | None
    document_page_limit: int | None
    monthly_cost_cap_usd: float | None
    trial_ends_at: datetime | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    features: dict[str, Any] = Field(default_factory=dict)


class DemoSeedResponse(ApiModel):
    workspace_id: str
    workspace_name: str
    documents: list[str]
    document_count: int
    evaluation_suites: list[str]
    agents: list[dict[str, str]]
    data_source_id: str | None
    backtest_id: str | None
    disclaimer: str
