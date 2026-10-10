# FINAGENT LAB — Product Requirements Document

> The product name is a placeholder. It is referenced through configuration
> (`PRODUCT_NAME`, `packages/config`) so it can be changed without touching code.

## 1. Mission

FINAGENT LAB is the **evaluation and observability layer for institutional financial AI**.

Institutions are deploying LLM agents into investment research without a rigorous way to
answer the only question that matters:

> **"Can I trust this AI agent to perform institutional-quality financial research?"**

The platform answers that with evidence: every agent action is captured, every claim is
checked against a source, every number is recomputed, every historical test is guarded
against look-ahead bias, and every run receives a reproducible, decomposable quality score.

Long-term vision: *the operating system for AI-native investment research*.

**Explicit non-goals for V1**

- Not an automated live trading system.
- Not a retail product; no financial advice is produced for retail users.
- The evaluation score is an **agent-quality score**, not a prediction of returns.

## 2. Users

| Persona | Primary needs | Key surfaces |
| --- | --- | --- |
| Portfolio Manager | Concise research, confidence, citations, agent comparison, audit trail | `/research/[id]`, `/benchmarks`, `/dashboard` |
| Quant Researcher | Python execution, datasets, statistical tests, backtests, reproducibility | `/backtests`, `/experiments`, `/datasets` |
| AI/ML Engineer | Model + agent configuration, eval suites, traces, latency, tokens, cost, failures | `/agents`, `/evaluations`, `/usage`, `/models` |
| Fund Administrator | Users, permissions, billing, API keys, data permissions, audit logs | `/settings/*`, `/admin` |

## 3. Core workflow

```
USER → WORKSPACE → AGENT (model + tools + data) → RESEARCH TASK → RUN
     → FULL TRACE → CLAIM/CITATION VERIFICATION → EVALUATION → SCORE
     → BACKTEST / HISTORICAL TEST → COMPARE → MONITOR
```

The primary interface is **not** a chat box. It is *task → agent → evidence → actions →
evaluation → result*. Chat may exist as a secondary affordance; it is not the product.

## 4. Product principles

1. **Evidence before conclusion.** A conclusion that cannot be traced to data, a
   calculation, a source and a reasoning step is treated as unsupported.
2. **Never trust the model's answer.** Deterministic and programmatic evaluators outrank
   LLM judges; LLM-as-judge is one down-weighted signal and is never used alone.
3. **No look-ahead, ever.** Historical evaluation enforces
   `publication_timestamp <= cutoff` at the retrieval and data-provider layer, not by
   prompt instruction.
4. **Honest data provenance.** A provider with no credentials reports `unavailable`.
   Demo/synthetic data is labelled `DEMO` in API payloads, UI badges and exports.
5. **Reproducibility is a feature.** Agent version, prompt version, model, tool set,
   dataset snapshot and parameters are recorded on every run.
6. **Multi-tenant isolation is non-negotiable.** Every row is scoped to an organization
   and (where applicable) a workspace; cross-tenant access is tested explicitly.

## 5. MVP scope (implemented in this repository)

Authentication (email/password, rotating refresh sessions, MFA, OAuth adapter seam) ·
organizations, workspaces, membership, RBAC (`OWNER`/`ADMIN`/`RESEARCHER`/`VIEWER`) ·
agent builder with immutable agent and prompt versions · model provider abstraction
(OpenAI/Anthropic/Google adapters + deterministic mock) · controlled tool registry with a
sandboxed Python tool · document ingestion (upload → validate → extract → chunk → embed →
index → retrieve) · citation system with support levels · research task templates · full
agent trace · evaluation engine (deterministic + programmatic + LLM judge) with
hallucination detection and configurable weighted scoring · golden dataset
`FINANCIAL_RESEARCH_BASIC_V1` (25 cases) · backtesting with costs, slippage, validation
warnings and train/validation/out-of-sample splits · experiments, benchmarks, leaderboard,
model/prompt comparison · multi-agent debate (bull/bear/skeptic/judge) · cost, latency and
token observability · audit log, API keys, rate limiting, webhooks, notifications · demo
tenant with **ACME Technologies** (fictional issuer, clearly labelled).

## 6. Success metrics

Tracked by the platform itself (`/usage`, `/dashboard`): time to first successful research
run · evaluation completion rate · mean accuracy and citation coverage · hallucination rate
· average research cost and duration · runs, active agents, evaluation suites.

Investment return is deliberately **not** a product KPI.

## 7. Documented assumptions

| # | Ambiguity | Decision |
| --- | --- | --- |
| 1 | Auth provider | Self-hosted credential auth behind an `AuthProvider` seam so Auth0/Clerk/WorkOS can replace it without touching routers. OAuth adapters report `unavailable` without client credentials. |
| 2 | Vector store | pgvector on PostgreSQL; a portable `Vector` column degrades to JSON + NumPy cosine similarity on SQLite (used by the test suite). |
| 3 | Worker | Celery + Redis in Docker; an `inline` job backend keeps the app functional (and tests hermetic) without a broker. |
| 4 | Python sandbox | Subprocess isolation with rlimits, import allow-list and network denial. Container/gVisor isolation is the documented production target. |
| 5 | Embeddings without credentials | Deterministic hashed bag-of-words provider, labelled `deterministic-mock`, so RAG works offline. Never presented as a production embedding model. |
| 6 | Billing | Plan/entitlement/usage model implemented; no payment processor is wired in the MVP. |
