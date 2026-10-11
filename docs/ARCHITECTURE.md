# Architecture

## 1. Repository layout

```
/apps
  /web                    Next.js 15 (App Router, TypeScript, Tailwind) — institutional UI
  /api                    FastAPI: HTTP surface, persistence, orchestration
/packages
  /core                   finagent_core — pure Python domain library (no DB, no HTTP)
/services
  /agent-runner           finagent_agent_runner — agent loop, tools, sandbox, multi-agent
  /evaluation-engine      finagent_evaluation — claims, citations, evaluators, scoring
  /backtesting-engine     finagent_backtesting — simulator, metrics, validation, splits
  /data-ingestion         finagent_ingestion — validate, extract, chunk, embed, quality
/infrastructure           Dockerfiles and the development compose stack
/docs                     PRD, architecture, database, security, evaluations, ...
/tests                    unit, api, security and end-to-end tests
```

There is deliberately no `packages/types`, `packages/ui` or `packages/config`. With a
single frontend consumer, a shared package adds a build step and a version boundary while
sharing nothing, and an unused package is a liability that drifts. The response contracts
live in `apps/web/lib/types.ts` (mirrored from `/openapi.json`) and the UI primitives in
`apps/web/components/primitives.tsx`. Extract them when a second consumer exists, not
before.

### Dependency direction (strict)

```
apps/web ──HTTP──▶ apps/api
                    ├─▶ services/agent-runner ──┐
                    ├─▶ services/evaluation-engine ─┤─▶ packages/core
                    ├─▶ services/backtesting-engine ┤
                    └─▶ services/data-ingestion ────┘
```

`packages/core` never imports SQLAlchemy, FastAPI or a service. The engines never import
`apps/api`. Engines are **pure**: they take dataclasses/Pydantic inputs and return results,
so they are unit-testable with no database, network or broker. All persistence and tenancy
enforcement lives in `apps/api`.

## 2. Runtime components

| Component | Responsibility |
| --- | --- |
| `web` | Next.js UI. Talks only to the API. Never sees provider API keys. |
| `api` | FastAPI: auth, RBAC, validation, CRUD, run orchestration, OpenAPI. |
| `worker` | Celery: agent runs, ingestion, evaluations, backtests, webhook retries. |
| `postgres` | System of record; `pgvector` for embeddings. |
| `redis` | Celery broker/result backend and rate-limit counters. |
| `sandbox` | Python tool execution (subprocess with rlimits today, container target). |

Everything comes up with `docker compose up`.

## 3. Request and job lifecycle

```
HTTP request
  → RequestContextMiddleware   assigns request_id, binds structured log context
  → RateLimitMiddleware        per-user / per-workspace / per-API-key buckets
  → auth dependency            session JWT or API key → Principal
  → workspace dependency       membership + role → WorkspaceContext
  → require_permission(...)    RBAC check, 403 with a safe message
  → router → service layer     business logic, validation, audit log
  → session                    tenant-scoped queries (organization_id filter)
```

Long work never happens in the request path. Routers create a durable row
(`research_runs`, `evaluations`, `backtest_runs`) with status `QUEUED`, then enqueue via
`JobQueue` (`celery` in production, `inline` in dev/tests). Status transitions:
`QUEUED → RUNNING → (SUCCEEDED | FAILED | CANCELLED)` with `error_code`/`error_message`
from the typed error taxonomy.

## 4. Agent execution

```
AgentRunner.run(spec, task, context)
  ├─ resolve AgentRunSpec (model, prompt version, tools, datasets, limits)
  ├─ build AsOfContext(cutoff)                      ← historical information lock
  ├─ loop (max_steps):
  │    ├─ ModelProvider.complete(...)  → tokens, latency, cost
  │    ├─ tool call? ToolRegistry.execute(name, args, context)   ← permission checked
  │    │      └─ recorded as TraceStep + ToolCall
  │    └─ otherwise finalize
  └─ RunResult { output, thesis?, evidence, trace, tool calls, usage }
```

The runner records the evidence the model was actually shown, so citation verification can
later compare claims against exactly that evidence.

## 5. Evaluation pipeline

```
RunResult
  → ClaimExtractor      sentence + numeric claim segmentation, claim typing
  → CitationResolver    claims → cited chunks; detects uncited and fabricated citations
  → SupportClassifier   DIRECTLY_SUPPORTED | PARTIALLY | INFERRED | UNSUPPORTED | CONTRADICTED
  → Evaluators
       deterministic: expected value/range, required fields, required/forbidden sources
       programmatic:  numeric recomputation, statistics, cutoff, cost/latency, overfitting
       llm_judge:     reasoning, completeness, relevance (down-weighted, never alone)
  → Scorer              per-dimension 0–100 + configurable weighted overall
  → EvaluationReport    dimension scores, failures with explanations, warnings
```

## 6. Historical information lock

`AsOfContext` (in `packages/core`) threads through every retrieval and data call, and
enforcement is structural:

- `documents` and `document_chunks` carry `publication_timestamp`;
- `DbDocumentRetriever` adds `publication_timestamp <= cutoff` (and excludes NULLs) in SQL;
- `FinancialDataProvider` methods take `as_of` and filter or raise;
- the backtester refuses signals that are not strictly older than the bar they trade on.

A violation raises `LookAheadViolation` or is reported as a blocking validation finding —
never a silent warning.

## 7. Observability

Structured JSON logs carry `request_id`, `run_id`, `evaluation_id`, `backtest_id`,
`organization_id`, `workspace_id`, `user_id` via `contextvars`. `model_runs` captures
provider, model, tokens, latency, estimated cost and request id. `usage_events` captures
billable units. `/usage` reports cost per task, per successful task and per accurate answer.

## 8. Failure handling

`packages/core/errors.py` defines the taxonomy (`PROVIDER_UNAVAILABLE`,
`DOCUMENT_PARSE_FAILED`, `AGENT_TIMEOUT`, `EVALUATION_FAILED`, `LOOK_AHEAD_VIOLATION`,
`SANDBOX_DENIED`, …). The API maps codes to safe messages; raw exceptions are logged, never
returned.

## 9. Extension seams

| Seam | Add an implementation by |
| --- | --- |
| `ModelProvider` | subclass + register in `packages/core/models/registry.py` |
| `FinancialDataProvider` | subclass + register in `packages/core/data/registry.py` |
| `EmbeddingProvider` | subclass + register in `packages/core/embeddings/registry.py` |
| `Tool` | declare schema + handler in `services/agent-runner/.../tools` and register |
| `Evaluator` | implement `Evaluator.evaluate()` and add to the default evaluator list |
| `AuthProvider` | implement the protocol in `apps/api/.../security/auth_provider.py` |
| `JobQueue` | implement `enqueue()` in `apps/api/.../jobs/queue.py` |
