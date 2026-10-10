# FINAGENT LAB

**The evaluation and observability layer for institutional financial AI.**

Build a financial research agent, run it against filings and market data, capture every
action it takes, verify every claim against the evidence it actually retrieved, score it
against a golden dataset with known answers, and backtest the resulting ideas under
explicit cost and execution-lag assumptions.

Built for hedge funds, asset managers, family offices and quant researchers who need an
audit trail rather than a chat transcript.

---

## What makes this different from a chat wrapper

| Problem | What this platform does |
| --- | --- |
| You cannot tell whether the answer is right | Output is decomposed into typed claims and each is checked against the retrieved evidence. Deterministic, so the same output always scores the same. |
| You cannot tell what it did | Every retrieval, tool call, calculation and model call is recorded in order with latency and cost. |
| Historical tests leak future information | A run with an information cutoff is restricted by SQL filters and provider-level checks, never by prompt instructions. |
| Backtests prove whatever you want | Commissions, slippage and a one-bar execution lag by default; train, validation and out-of-sample windows reported separately and never averaged. |

---

## Three guarantees

1. **Nothing simulated is presented as live.** Output from the deterministic local provider
   or the demo corpus carries `used_mock_model`, `used_demo_data`, `is_mock` or `is_demo`,
   and the UI badges every one of them.
2. **Historical research cannot see the future.** Enforced structurally. Evidence with an
   unknown publication timestamp is excluded rather than assumed admissible.
3. **A score is a research-quality score.** It measures evidence grounding, citation
   accuracy and numerical correctness. It is not a prediction of investment returns, and
   nothing in the product implies otherwise.

Customer data is isolated and is not used for model training unless explicitly authorized.

---

## Running it

### With Docker (Postgres + pgvector, Redis, API, Celery worker, web)

```bash
cp .env.example .env            # optional: add provider keys
docker compose -f infrastructure/docker-compose.yml up --build
```

Then open <http://localhost:3000>. The API's interactive documentation is at
<http://localhost:8000/docs>.

### Locally, with no external services at all

The platform is designed to run end to end offline, because the security tests must be
verifiable on any machine. SQLite stands in for Postgres, a deterministic local provider
stands in for a language model, and a hashed bag-of-words embedder stands in for a vector
model. All three are labelled as simulated wherever their output appears.

```bash
python -m venv .venv && source .venv/bin/activate
pip install ./packages/core ./services/agent-runner ./services/evaluation-engine \
            ./services/backtesting-engine ./services/data-ingestion ./apps/api
pip install pytest httpx ruff

export DATABASE_URL="sqlite:///./finagent.db"
export SECRET_KEY="local-development-secret-key"
export JOB_BACKEND=inline

python -m finagent_api.cli init-db
python -m finagent_api.cli demo-flow        # seed → run → evaluate → backtest, end to end
uvicorn finagent_api.main:app --reload
```

In another shell:

```bash
cd apps/web && npm install
FINAGENT_API_URL=http://localhost:8000 npm run dev
```

### Tests

```bash
python -m pytest tests/security -v     # the seven critical controls
python -m pytest                       # everything
```

---

## Repository layout

```
apps/
  api/            FastAPI service: tenancy, persistence, authorisation, HTTP surface
  web/            Next.js 15 App Router front end
packages/
  core/           Domain core: providers, cutoff, numerics, demo dataset, errors, logging
services/
  agent-runner/        Agent loop, tool registry, Python sandbox, multi-agent debate
  evaluation-engine/   Claim extraction, verification, evaluators, scoring, golden dataset
  backtesting-engine/  Simulator, costs, metrics, splits, overfitting checks
  data-ingestion/      Parsing, chunking, embedding, indexing
infrastructure/   Dockerfiles and the development compose stack
docs/             Architecture, database, evaluation, backtesting, security, API
tests/            unit · api · security · e2e
```

`packages/core` and the four services never import SQLAlchemy or FastAPI. All persistence
and tenancy live in `apps/api`, which is what lets the research engines be tested without
infrastructure. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## The seven controls that must never regress

`tests/security/test_critical_controls.py` asserts each of these end to end:

1. An agent cannot access another workspace's data (and a cross-tenant request returns
   `404`, not `403`, so the response cannot confirm the workspace exists).
2. An agent cannot retrieve information published after its cutoff.
3. An unsupported financial claim is flagged.
4. An incorrect calculation is flagged.
5. A backtest that trades on the bar that produced its signal is rejected as invalid.
6. A deleted document cannot be retrieved.
7. A provider API key never appears in any response.

---

## Documentation

| Document | Contents |
| --- | --- |
| [docs/PRD.md](docs/PRD.md) | Product definition, users, principles, scope boundaries |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Dependency direction, services, request lifecycle |
| [docs/DATABASE.md](docs/DATABASE.md) | Every table, portability strategy, migration policy |
| [docs/AGENTS.md](docs/AGENTS.md) | Agent schema, versioning, tools, the sandbox |
| [docs/EVALUATIONS.md](docs/EVALUATIONS.md) | Claim verification, dimensions, weighting, golden dataset |
| [docs/BACKTESTING.md](docs/BACKTESTING.md) | Simulation assumptions, splits, validity rules |
| [docs/SECURITY.md](docs/SECURITY.md) | Tenancy, authentication, RBAC, sandbox, data handling |
| [docs/DATA_PROVIDERS.md](docs/DATA_PROVIDERS.md) | Provider abstraction and the mock/demo policy |
| [docs/API.md](docs/API.md) | Endpoint reference, error contract, pagination |
| [docs/ROADMAP.md](docs/ROADMAP.md) | What is built, what is next, what is deliberately excluded |

---

## What this platform will not do

- It will not predict returns, and no score should be read as a forecast.
- It will not give investment advice, and it is not for retail users.
- It will not trade. There is no live execution path, by design.
- It will not present simulated output as real.
- It will not claim a backtest is valid unless it uses timestamped historical data with a
  non-zero execution lag.
