# Roadmap

**done** = implemented and tested here · **partial** = architecture plus a working subset ·
**planned** = designed, not built.

## Phase 1 — Foundation · done
Monorepo, PostgreSQL schema + migration, authentication, organizations/workspaces, RBAC,
FastAPI backend, Next.js shell, Docker Compose, CI, structured logging.
*Acceptance*: sign up, create a workspace, invite a member, log in. ✔

## Phase 2 — Agent engine · done
Agent schema, agent builder, immutable agent and prompt versions, model provider
abstraction, controlled tool registry, agent runner, trace system.
*Acceptance*: create an agent and run a task with every action captured. ✔

## Phase 3 — Data · done
Upload → validate → extract → chunk → embed → index → retrieve, pgvector, page-level
citations, SEC EDGAR and market-data provider abstraction, labelled demo provider.
*Acceptance*: the agent answers from uploaded documents and cites page numbers. ✔

## Phase 4 — Evaluation · done
Golden dataset `FINANCIAL_RESEARCH_BASIC_V1` (25 cases), claim extraction, citation
verification, hallucination detection, LLM judge, programmatic evaluators, weighted scoring.
*Acceptance*: a research run receives a reproducible score. ✔

## Phase 5 — Observability · done
Trace viewer, token/latency/cost tracking, tool-usage stats, failure analysis, usage events,
request/run/evaluation correlation ids.
*Acceptance*: a user can reconstruct exactly what the agent did. ✔

## Phase 6 — Backtesting · done
Portfolio simulator, transaction costs, slippage, position limits, full metric set,
look-ahead/survivorship/leakage validation, train/validation/out-of-sample splits with
automatic overfitting assessment.
*Acceptance*: a reproducible historical strategy evaluation. ✔

## Phase 7 — Benchmarking · done
Agent, model and prompt comparison, experiment tracking, configurable leaderboard.
*Acceptance*: determine which agent/model/prompt performs best. ✔

## Phase 8 — Multi-agent · done (single round)
Bull, bear, skeptic and judge roles with orchestration and a structured debate object.
**Planned**: multi-round debate, editor/risk agents, shared scratchpads, cross-agent budgets.
*Acceptance*: multiple agents independently research a thesis and critique one another. ✔

## Phase 9 — Enterprise · partial
Done: RBAC, audit logs, API keys with scopes, rate limiting, usage metering, plan limits,
HMAC-signed webhooks, notifications, private data isolation, customer-feedback module.
Planned: SAML/OIDC SSO (seam exists), SCIM, payment processor, private VPC deployment
(Terraform skeletons), malware-scanner integration (interface exists), signed audit export.

## Verified configurations

| Configuration | Status |
| --- | --- |
| SQLite · inline jobs · deterministic providers | 113 tests, full demo flow, full UI walkthrough |
| PostgreSQL 16 + pgvector · inline jobs | 113 tests, full demo flow, HNSW index confirmed in the query plan |
| PostgreSQL + Redis + Celery worker · web UI | research runs, suite evaluations and backtests executed on a worker; pages update themselves |
| Vendor model and data providers | **not exercised** — no credentials were available. The provider abstraction, availability reporting and cost estimation are in place and every provider reports itself unavailable rather than falling back silently. |

## Beyond
Portfolio monitoring · investment-committee workflows · continuous earnings agents ·
alternative data · options/credit/macro research · PE diligence · M&A analysis · compliance
review · agent marketplace.

Explicitly **out of scope**: automated live trading.
