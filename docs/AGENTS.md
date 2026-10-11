# Agents

---

## 1. What an agent is

A model, a set of instructions, a tool allow-list, and the data it may read. Nothing
ambient: an agent that has not been given `MARKET_DATA` cannot reach market data, even if
the model asks for it by name.

```
Agent                 identity and current pointer
 └─ AgentVersion      immutable configuration snapshot (config_hash)
     ├─ AgentPrompt   instruction text, versioned separately and deduplicated by hash
     ├─ AgentTool     the allow-list
     ├─ AgentModel    provider, model key, role, parameters
     └─ AgentDataset  bound datasets, documents and data sources
```

---

## 2. Versioning

**Agents are never edited in place.** Every configuration change publishes a new
`AgentVersion` with its own `config_hash`, and a run records the version id it executed.

This is what makes "did v3 actually help?" answerable. Without it, a run from last month
points at a configuration that no longer exists, and every comparison is guesswork.

Prompts are versioned separately and deduplicated by content hash, so changing the model
while keeping the prompt does not create a spurious prompt version — which keeps the
prompt-comparison view honest.

> Asserted by `tests/api/test_api_surface.py::TestAgentBuilder::test_updating_an_agent_creates_a_new_version`.

---

## 3. Tools

| Tool | Category | Network | Deterministic |
| --- | --- | --- | --- |
| `DOCUMENT_SEARCH` | research | no | yes |
| `SEC_SEARCH` | research | yes | no |
| `FINANCIAL_STATEMENTS` | fundamentals | yes | no |
| `MARKET_DATA` | market | yes | no |
| `CALCULATOR` | quant | no | yes |
| `PYTHON` | quant | no | yes |
| `BACKTEST` | quant | no | yes |
| `PORTFOLIO_ANALYSIS` | quant | no | yes |

Every tool declares a JSON schema and the permissions it requires. `ToolRegistry.execute`
is the only path by which a tool can run, and it refuses anything outside the version's
allow-list before validating arguments:

```python
if name not in context.allowed_tools:
    raise ToolNotPermittedError(...)
```

A tool that raises an unexpected exception is wrapped in `ToolFailedError`; the raw
exception never reaches the model or the client.

---

## 4. The Python sandbox

Quantitative research needs real code execution. The constraints are documented in
[SECURITY.md](SECURITY.md#5-code-execution); the short version:

- Separate subprocess in its own process group, with CPU, memory and file-size rlimits and
  a wall-clock timeout.
- No network: socket construction raises.
- No filesystem: `open` is replaced, and the working directory is a throwaway temp dir.
- Import allow-list enforced twice — a static AST scan before execution, and a restricted
  `__builtins__` inside the sandbox namespace.

`pandas` and `numpy` are available, because analysis code that cannot use them is not
analysis code. The import guard is installed in the sandbox namespace rather than by
deleting names from the `builtins` module, because deleting `exec` and `compile` globally
breaks pandas' own internals.

Results are returned by assigning to a `result` dict. Standard output is captured and
returned alongside it.

---

## 5. The run loop

`services/agent-runner/finagent_agent_runner/runner.py`

```
plan → retrieve → compute → challenge → conclude
```

Each iteration: the model is given the task, the evidence so far and the tool schemas; it
either requests a tool call or produces a final answer. The loop stops at the version's
`max_steps` or `timeout_seconds`, whichever comes first, and a step-limit stop is recorded
as `AGENT_STEP_LIMIT` rather than reported as a normal completion.

Everything is recorded: `AgentTraceStep` per action with latency, tokens and estimated
cost; `ToolCall` per invocation with arguments and result; `ModelRun` per model call;
`RunEvidence` per retrieved chunk; `AgentMessage` for the full conversation.

---

## 6. Reproducibility

Each run records a `reproducibility_key` derived from the agent version's `config_hash`,
the model, the task and the information cutoff. "Reproduce" re-executes the exact recorded
configuration, and the reproducibility dimension measures how closely the outputs agree.

A model with non-zero temperature is not expected to be bit-identical — that is a property
of the model, and the platform measures it rather than assuming it away. The deterministic
local provider *is* bit-identical, which is what makes the measurement calibratable.

> Asserted by `test_reproducing_a_run_produces_the_same_answer`.

---

## 7. Multi-agent debate

`DebateOrchestrator` runs four roles against the same task:

| Role | Brief |
| --- | --- |
| `bull` | Build the strongest supported positive case |
| `bear` | Build the strongest supported negative case |
| `skeptic` | Attack the evidence quality of both |
| `judge` | Decide which side is *better supported* |

Each role is a full child run with its own trace and evidence, linked to the parent by
`parent_run_id` and labelled with `debate_role`. Child runs are hidden from the main run
list but individually inspectable.

The judge decides which side is better *supported by evidence*, not which side is right
about the future. The verdict carries the disclaimer that a debate is an argument-quality
signal, not a recommendation.

> Asserted by `test_a_debate_records_each_role_as_its_own_run`.

---

## 8. The deterministic local provider

With no vendor credentials, `MockModelProvider` lets the entire platform run end to end.
It is **not** a language model — it is a rule-based analyst simulator, and it is honest
about that:

- Reports `ProviderStatus.MOCK`, never `AVAILABLE`.
- Sets `is_mock=True` on every response; the API sets `used_mock_model` on the run and the
  UI badges it as **Simulated model**.
- Composes output **only** from tool results the agent actually retrieved. It never invents
  a financial figure.
- Addresses each of the task template's required output fields explicitly, and says
  "not established by the retrieved evidence" when the corpus does not support one —
  because saying so is the correct answer and inventing a value to satisfy the contract is
  not.

`mock-analyst-weak` is the deliberately flawed counterpart: it omits citations and asserts
one fabricated growth figure. It exists so the evaluators can be *proven* to catch
failures, and it is labelled "Never use it for research" in the model catalog.
