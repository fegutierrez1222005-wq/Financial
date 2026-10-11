/** Response shapes mirrored from the API's OpenAPI document. */

export type Workspace = {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description: string | null;
  use_case: string | null;
  default_information_cutoff: string | null;
  is_demo: boolean;
  created_at: string;
  role: string | null;
};

export type AgentVersion = {
  id: string;
  agent_id: string;
  version_number: number;
  prompt_version_id: string | null;
  model: string;
  temperature: number;
  max_tokens: number;
  max_steps: number;
  timeout_seconds: number;
  output_format: string;
  evaluation_suite_keys: string[];
  change_note: string | null;
  config_hash: string;
  created_at: string;
  tools: string[];
  bindings: Record<string, string[]>;
};

export type Agent = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  archetype: string;
  current_version_id: string | null;
  is_demo: boolean;
  tags: string[];
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  current_version: AgentVersion | null;
  version_count: number;
};

export type ResearchRun = {
  id: string;
  workspace_id: string;
  task_id: string | null;
  agent_id: string;
  agent_version_id: string | null;
  parent_run_id: string | null;
  debate_role: string | null;
  model: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  model_calls: number;
  tool_call_count: number;
  estimated_cost_usd: number;
  output_text: string | null;
  thesis: Record<string, unknown> | null;
  confidence: number | null;
  citation_coverage: number | null;
  hallucination_rate: number | null;
  evidence_count: number;
  information_cutoff: string | null;
  used_mock_model: boolean;
  used_demo_data: boolean;
  warnings: string[];
  error_code: string | null;
  error_message: string | null;
  reproducibility_key: string | null;
  reproduced_from_run_id: string | null;
  created_at: string;
};

export type ResearchTask = {
  id: string;
  template_key: string;
  title: string;
  question: string;
  inputs: Record<string, unknown>;
  required_output_fields: string[];
  output_format: string;
  information_cutoff: string | null;
  created_at: string;
};

export type TraceStep = {
  sequence: number;
  kind: string;
  action: string | null;
  tool_name: string | null;
  model: string | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
};

export type Evidence = {
  chunk_ref: string;
  document_id: string | null;
  document_name: string | null;
  page_number: number | null;
  text: string;
  similarity: number | null;
  publication_timestamp: string | null;
  source: string | null;
  is_demo: boolean;
};

export type RunDetail = {
  run: ResearchRun;
  task: ResearchTask | null;
  plan: Array<{ step_index: number; kind: string; title: string; status: string }>;
  trace: TraceStep[];
  evidence: Evidence[];
  citations: Array<Record<string, unknown>>;
  messages: Array<{ sequence: number; role: string; content: string; tool_name: string | null }>;
  tool_calls: Array<{
    tool_name: string;
    arguments: Record<string, unknown>;
    status: string;
    latency_ms: number | null;
    error_code: string | null;
    error_message: string | null;
  }>;
  model_runs: Array<{
    provider: string;
    model: string;
    input_tokens: number | null;
    output_tokens: number | null;
    latency_ms: number | null;
    estimated_cost_usd: number | null;
    is_mock: boolean;
  }>;
  evaluations: Array<{
    id: string;
    kind: string;
    status: string;
    overall_score: number | null;
    hallucination_rate: number | null;
    citation_coverage: number | null;
  }>;
};

export type Evaluation = {
  id: string;
  kind: string;
  run_id: string | null;
  suite_key: string | null;
  agent_id: string | null;
  agent_version_id: string | null;
  status: string;
  overall_score: number | null;
  pass_rate: number | null;
  case_count: number | null;
  passed_count: number | null;
  hallucination_rate: number | null;
  citation_coverage: number | null;
  judge_model: string | null;
  judge_is_mock: boolean;
  warnings: string[];
  summary: Record<string, unknown>;
  finished_at: string | null;
  duration_ms: number | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
};

export type EvaluationDetail = {
  evaluation: Evaluation;
  scores: Array<{ dimension: string; score: number; weight: number; detail: Record<string, unknown> }>;
  results: Array<{
    case_key: string | null;
    run_id: string | null;
    passed: boolean;
    score: number | null;
    expected: string | null;
    actual: string | null;
    failure_code: string | null;
    failure_title: string | null;
    failure_reason: string | null;
    severity: string | null;
    dimension: string | null;
    evaluator: string | null;
  }>;
  claims: Array<{
    text: string;
    kind: string;
    section: string | null;
    support_level: string | null;
    cited_chunk_refs: string[];
    evidence_quote: string | null;
    similarity: number | null;
    explanation: string | null;
  }>;
  score_interpretation: string;
};

export type Backtest = {
  id: string;
  name: string;
  description: string | null;
  universe: string[];
  strategy: Record<string, unknown>;
  start_date: string;
  end_date: string;
  rebalance_frequency: string;
  transaction_cost_bps: number;
  slippage_bps: number;
  initial_capital: number;
  signal_lag_days: number;
  benchmark_symbol: string | null;
  test_split_use_count: number;
  created_at: string;
};

export type BacktestSplit = {
  id: string;
  split: string;
  status: string;
  is_valid: boolean;
  start_date: string | null;
  end_date: string | null;
  metrics: Record<string, number>;
  findings: Array<{ code?: string; severity?: string; title?: string; message?: string }>;
  rebalance_count: number;
  trade_count: number;
  is_demo_data: boolean;
  equity_curve: Array<{ date: string; equity: number; drawdown_pct: number; exposure_pct: number }>;
  trades: Array<Record<string, unknown>>;
};

export type BacktestDetail = {
  backtest: Backtest;
  runs: BacktestSplit[];
  overfitting: Record<string, unknown> | null;
  test_split_use_count: number;
  reporting_note: string;
  disclaimer: string;
};

export type FinDocument = {
  id: string;
  filename: string;
  title: string | null;
  extension: string | null;
  size_bytes: number;
  page_count: number | null;
  chunk_count: number;
  status: string;
  publication_timestamp: string | null;
  source_label: string | null;
  document_type: string | null;
  ticker: string | null;
  embedding_model: string | null;
  embedding_is_mock: boolean;
  is_demo: boolean;
  error_message: string | null;
  warnings: string[];
  created_at: string;
};

export type ScoreboardEntry = {
  rank: number;
  evaluation_id: string;
  agent_id: string;
  agent_name: string | null;
  version_number: number | null;
  model: string | null;
  suite_key: string | null;
  overall_score: number | null;
  pass_rate: number | null;
  hallucination_rate: number | null;
  citation_coverage: number | null;
  dimension_scores: Record<string, number>;
  judge_is_mock: boolean;
  evaluated_at: string | null;
};

export type ToolDescriptor = {
  name: string;
  title: string;
  description: string;
  category: string;
  requires_network: boolean;
  is_deterministic: boolean;
  available: boolean;
  unavailable_reason: string | null;
};

export type ModelDescriptor = {
  key: string;
  provider: string;
  display_name: string;
  context_window: number;
  input_cost_per_1k: number;
  output_cost_per_1k: number;
  available: boolean;
  is_mock: boolean;
  notes: string | null;
};

export type Dashboard = {
  headline: Record<string, number>;
  research_efficiency: Record<string, unknown>;
  product_metrics: Record<string, unknown>;
  recent_runs: Array<Record<string, unknown>>;
  agent_performance: Array<{
    agent_id: string;
    agent_name: string;
    runs: number;
    mean_score: number | null;
    mean_cost_usd: number;
    mean_duration_ms: number;
  }>;
  evaluation_failures: Array<{
    evaluation_id: string;
    case_key: string | null;
    run_id: string | null;
    code: string | null;
    title: string | null;
    reason: string | null;
    dimension: string | null;
  }>;
  cost_trend: Array<{ date: string; cost_usd: number; runs: number }>;
  usage: Record<string, never> | Record<string, unknown>;
};

export type ProviderStatus = {
  available_models: Array<Record<string, unknown>>;
  unavailable_models: Array<{ key: string; provider: string; display_name: string; reason: string }>;
  data_providers: Array<{
    key: string;
    display_name: string;
    status: string;
    is_demo: boolean;
    capabilities: string[];
    requires_credentials: boolean;
    docs_url?: string | null;
  }>;
  embeddings: Array<{ key: string; display_name: string; status: string; is_mock: boolean }>;
  credentials_configured: Record<string, boolean>;
  sandbox: Record<string, unknown>;
  judge: { model: string | null; is_mock: boolean; note: string };
  notice: string;
};
