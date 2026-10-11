# Database

PostgreSQL 16 + `pgvector`. SQLAlchemy 2.0 ORM, Alembic migrations.

Identifiers are UUIDv4 stored through a portable `GUID` type. Timestamps use a portable
`UTCDateTime` type that normalises to timezone-aware UTC on every dialect — SQLite would
otherwise return naive datetimes and silently break expiry comparisons.

## Tenancy rules

1. Every domain table carries `organization_id`.
2. Research-context tables also carry `workspace_id`.
3. Reads are tenant-filtered in the query, never in Python.
4. Deletes of tenant-visible content are **soft** (`deleted_at`) so audit trails and past
   traces survive; retrieval filters `deleted_at IS NULL` (critical test #6).

## Table inventory

### Identity and tenancy
`users` (email, password_hash, mfa_enabled, mfa_secret_encrypted, is_platform_admin,
failed_login_count, locked_until) · `organizations` (slug, plan, data_training_opt_in) ·
`organization_members` · `workspaces` (slug, use_case, default_information_cutoff, is_demo)
· `workspace_members` (role) · `invitations` (token_hash, expires_at) · `sessions`
(refresh_token_hash, expires_at, revoked_at, mfa_satisfied) · `oauth_identities` ·
`api_keys` (key_prefix, key_hash, scopes, role, revoked_at).

### Agents
`agents` (name, archetype, current_version_id) · `agent_versions` (**immutable**: model,
temperature, max_tokens, max_steps, output_format, risk_constraints, prompt_version_id,
config_hash) · `agent_prompts` (version_number, content, content_hash) · `agent_tools`
(tool_name, permissions) · `agent_models` · `agent_datasets`.

`POST /agents/{id}/versions` creates version *n+1*; versions are never mutated.

### Data and documents
`data_sources` (provider_key, status, is_demo, capabilities) · `data_connectors`
(secret_encrypted) · `data_permissions` · `datasets` (schema_json, coverage, quality_score,
quality_report) · `dataset_snapshots` (content_hash) · `documents` (sha256, page_count,
status, publication_timestamp, embedding_model, malware_scan_status, deleted_at) ·
`document_chunks` (page_number, text, publication_timestamp, `embedding vector(1536)`) ·
`citations` (claim → chunk, support_level, quote).

### Research and traces
`research_tasks` (template_key, inputs, required_output_fields, information_cutoff) ·
`research_runs` (agent_version_id, model, status, timing, tokens, cost, output, thesis,
confidence, citation_coverage, hallucination_rate, reproducibility_key, debate_role) ·
`research_steps` · `agent_traces` · `agent_trace_steps` (sequence, kind, action, input,
output, latency, tokens, error) · `agent_messages` · `tool_calls` · `model_runs` ·
`run_evidence` (the exact passages shown to the agent) · `claims` (support verdicts).

### Evaluation
`evaluation_suites` (key, version, weights) · `evaluation_cases` (question,
expected_answer, expected_value, acceptable range, required/forbidden sources, difficulty,
category, evaluation_method) · `evaluations` (kind, status, overall_score, pass_rate,
hallucination_rate, citation_coverage, judge_model, summary) · `evaluation_results`
(per-case outcome and failure explanation) · `evaluation_scores` (per-dimension score and
applied weight).

### Backtesting
`backtests` (universe, strategy, window, costs, slippage, capital, limits, signal_lag_days,
split_config, test_split_use_count) · `backtest_runs` (split, is_valid, metrics_summary,
findings, overfitting, data_fingerprint) · `backtest_trades` · `backtest_metrics` ·
`backtest_equity_points`.

### Experiments and benchmarking
`experiments` (variable, suite_key, configuration, results_summary, conclusion) ·
`experiment_runs` (arm) · `models` (catalog with availability and estimated pricing) ·
`benchmarks` · `benchmark_entries` (rank, dimension scores, cost, research_efficiency).

### Platform
`audit_logs` · `alerts` · `notifications` · `webhooks` / `webhook_deliveries` (HMAC
signature, retry state) · `subscriptions` (plan limits, cost cap) · `usage_events` ·
`rate_limit_events` · `feedback_entries`.

`run_evidence` is an addition to the schema listed in the specification: citation
verification must compare claims against the evidence available *at run time*, which cannot
be reconstructed from the live index after documents change.

## Enumerations

Stored as strings rather than PostgreSQL enums so adding a value needs no type migration:
`WorkspaceRole`, `RunStatus`, `ClaimSupport`, `EvaluationDimension`, `TaskTemplate`,
`ToolName`, `OutputFormat`, `DocumentStatus`, `BacktestSplit`, `RebalanceFrequency`,
`UsageKind`, `AlertSeverity`.

## Migrations

```bash
cd apps/api
alembic upgrade head                        # apply
alembic revision --autogenerate -m "..."    # author
```

The baseline revision `0001_initial_schema` installs `pgvector`, builds the full schema
from ORM metadata (so baseline and models cannot drift), and creates an HNSW cosine index
on `document_chunks.embedding`. HNSW rather than IVFFlat because IVFFlat has to be built
against existing rows to choose its list count, and the index is created on an empty table.

pgvector is a hard requirement on PostgreSQL: `Vector` maps to a `vector(1536)` column
whenever the Python package is importable, so the table cannot be created without the
extension. The migration says so plainly rather than failing later with
`type vector does not exist`.

### Running the test suite against PostgreSQL

The suite defaults to SQLite so it needs no infrastructure, but the production dialect is
where dialect-specific defects live — two were found this way: `cosine_distance` was
missing from the `Vector` decorator, so every similarity query silently fell back to a
sequential scan; and a non-finite `profit_factor` was accepted by SQLite and rejected by
PostgreSQL's JSONB.

```bash
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=finagent -e POSTGRES_USER=finagent \
  -e POSTGRES_DB=finagent pgvector/pgvector:pg16
TEST_DATABASE_URL="postgresql+psycopg://finagent:finagent@localhost:5432/finagent" pytest
```

The fixture drops and recreates the `public` schema first, so a previous run cannot mask a
missing migration. CI runs the suite on both dialects.
