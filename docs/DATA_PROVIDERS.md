# Data providers

---

## 1. The rule

> If an external API is unavailable: create a provider abstraction, create a mock
> provider, clearly label mock/demo data, and never pretend mock data is live.

Every provider implements a capability-declaring interface and reports its own status. A
provider with no credentials is `unavailable` and cannot be selected. It never silently
degrades to synthetic data, because a silent fallback is how a demo becomes a false
production report.

---

## 2. Model providers

| Key | Models | Status without credentials |
| --- | --- | --- |
| `openai` | gpt-4o, gpt-4o-mini, gpt-4.1, o4-mini | `unavailable` |
| `anthropic` | claude-sonnet-4, claude-opus-4, claude-3-5-haiku | `unavailable` |
| `google` | gemini-2.5-pro, gemini-2.5-flash | `unavailable` |
| `mock` | mock-analyst-v1, mock-analyst-weak, mock-judge-v1 | `mock` — always available |

`resolve_model` raises `ModelUnavailableError` when a requested model's provider has no
credentials. It does **not** substitute a different model: a run must never execute on a
model other than the one recorded on the agent version, because the recorded version is
what every later comparison depends on.

`MODEL_CATALOG` carries operator-configurable cost estimates in USD per 1,000 tokens.
These are estimates for cost observability, not billing-grade figures, and they are
labelled as estimates wherever they surface. Override with `FINAGENT_MODEL_PRICES` (JSON)
to match a negotiated rate card.

---

## 3. Market and filing data

| Key | Source | Requires |
| --- | --- | --- |
| `sec_edgar` | SEC EDGAR filings and company facts | `SEC_USER_AGENT` (a contact string, per SEC policy) |
| `alpha_vantage` | Daily adjusted prices, fundamentals | `ALPHA_VANTAGE_API_KEY` |
| `polygon` | Aggregate bars | `POLYGON_API_KEY` |
| `demo` | The fictional ACME dataset | nothing — always available, always labelled |

Each provider declares capabilities (`PRICES`, `FUNDAMENTALS`, `FILINGS`, `COMPANY_FACTS`)
and refuses a request for a capability it does not support rather than returning an empty
result that looks like "no data exists".

**Every provider enforces the information cutoff.** `_enforce_cutoff` is called before any
record is returned, so the control holds even for a provider added later.

---

## 4. Embeddings

| Key | Model | Requires |
| --- | --- | --- |
| `openai` | text-embedding-3-small (1536 dims) | `OPENAI_API_KEY` |
| `deterministic` | Hashed bag-of-words, 1536 dims | nothing |

The deterministic provider is a hashed bag-of-words projection — a real, reproducible
vector space, but not a trained semantic model. Documents indexed with it are flagged
`embedding_is_mock = true` and the UI badges them **Local embeddings**, because retrieval
quality is materially lower and a reader comparing results needs to know that.

Switching embedding providers requires re-indexing. Vectors from different models are not
comparable, and silently mixing them would quietly corrupt every similarity score.

---

## 5. The demo dataset

`packages/core/finagent_core/data/demo_dataset.py`

Eight fictional issuers, with ACME Technologies as the fully modelled one:

- **Statements** — FY2021–FY2023 annual income, balance sheet and cash flow, plus
  Q1 2022 – Q4 2023 quarterly income. Internally consistent: quarters sum to the annual
  figure, gross profit reconciles, the balance sheet balances. Asserted by
  `tests/unit/test_core_primitives.py::TestDemoDataset`.
- **Documents** — 10-Ks, 10-Qs, earnings releases, an earnings call transcript and an
  internal memo. **The prose is generated from the same tables**, so a figure quoted in a
  filing is the figure in the statements. That is what makes citation verification do real
  work rather than matching against text written to be matched.
- **Prices** — a seeded random walk from a 2018 anchor, deterministic across processes.
- **Factors** — earnings yield, gross margin and accruals with a 45-day publication lag.

Every page carries a `DEMO DATA — … is a fictional issuer` banner, every profile
description contains the word "fictional", every document, chunk, price bar and factor row
sets `is_demo = true`, and the UI badges all of it.

The demo issuer is fictional on purpose. Using a real company's name with synthetic figures
would produce documents that look like filings and are not.

---

## 6. Adding a provider

1. Subclass the relevant base in `packages/core/finagent_core/data/base.py` or
   `models/base.py`.
2. Declare `key`, `display_name`, `capabilities` and `requires_credentials`.
3. Implement `status()` honestly — `UNAVAILABLE` without credentials, never `AVAILABLE`.
4. Call `self._require(capability)` at the top of every data method.
5. Call `self._enforce_cutoff(...)` before returning any timestamped record.
6. Register it in the relevant `build_default_*_registry`.
7. Add the credential to `Settings` and to `.env.example`, and add a boolean to
   `provider_status_summary()`. **Never** return the value from an endpoint.
