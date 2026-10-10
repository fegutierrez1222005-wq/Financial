# Evaluation

How the platform decides whether a piece of research is any good — and why the answer is
not "we asked another model."

---

## 1. The pipeline

```
RunResult
   │
   ├─ extract_claims()        deterministic decomposition into typed assertions
   │
   ├─ verify_claims()         each claim ↔ the evidence the agent actually retrieved
   │
   ├─ evaluators              15 evaluators over 16 dimensions
   │
   └─ Scorer.score()          weighted, renormalised, 0–100
```

Nothing in the first two stages involves a language model. The same output always produces
the same claims and the same verdicts, which is what makes a score comparable across runs,
across agents and across time.

---

## 2. Claim extraction

`services/evaluation-engine/finagent_evaluation/claims.py`

Output is split into sentences and each is typed, because different kinds of statement
carry different obligations:

| Kind | Obligation |
| --- | --- |
| `FACTUAL` | Must be supported by cited evidence. |
| `FORWARD_LOOKING` | The *basis* must be cited; the outcome cannot be. Projections are not hallucinations. |
| `ASSUMPTION` | Explicitly labelled. Must not be presented as fact — and must not be counted as one. |
| `UNKNOWN` | An explicit admission of missing evidence. Saying "the evidence does not establish this" is correct behaviour, not a failure. |
| `META` | A statement about the research process, not about the world. |

Classification uses the section heading first (`### Assumptions` makes everything under it
an assumption), then sentence-level markers. Citation markers of the form
`[Source: ACME FY2023 10-K, page 1 | chunk:<id>]` are parsed out of the claim before
numbers are extracted — otherwise the page number would be read as a reported figure.

Fragments shorter than five words are not assertions and are dropped.

---

## 3. Verification

`services/evaluation-engine/finagent_evaluation/verification.py`

Each support-requiring claim is scored against the evidence set:

| Verdict | Meaning |
| --- | --- |
| `DIRECTLY_SUPPORTED` | Cited chunk contains the statement and every number in it matches. |
| `PARTIALLY_SUPPORTED` | Cited chunk is on topic but not every figure is confirmed. |
| `INFERRED` | The claim is supported by retrieved evidence the agent did not cite. A citation failure, not a factual one — and the distinction matters. |
| `CONTRADICTED` | Evidence states a different value for the same quantity. |
| `UNSUPPORTED` | Nothing in the retrieved evidence backs it. |

Two things the verifier refuses to be fooled by:

- **Fabricated citations.** A citation pointing at a chunk id that is not in the evidence
  set is counted in `fabricated_citation_count`. An invented source is worse than no
  source, because it looks checkable.
- **Unit confusion.** Numbers carry units (`finagent_core.numeric`). "18.0%" and
  "$18.0 million" are never treated as the same figure, and a scaled money figure is
  normalised to its base unit so `$4,820.0 million` cannot be compared against a bare
  `4820`.

`hallucination_rate` is the share of support-requiring claims that nothing backs.
Assumptions, unknowns and meta-statements are excluded from the denominator, because
penalising an agent for correctly flagging uncertainty would train exactly the wrong
behaviour.

---

## 4. Evaluators and their weight

There are three kinds, and their relative trust is explicit:

| Kind | Weight | What it is |
| --- | --- | --- |
| `DETERMINISTIC` | 1.00 | A known answer, a citation rule, a required field. No judgement. |
| `PROGRAMMATIC` | 0.90 | Recomputation and consistency checks — the calculator's arithmetic, train/test degradation, tool efficiency. |
| `LLM_JUDGE` | 0.35 | A model's opinion on reasoning quality. |

When two evaluators score the same dimension, the result is a trust-weighted mean. An LLM
judge scoring 100 cannot pull a deterministic 0 above about 26 — which is the point. A
judge is a tie-breaker on qualities that cannot be checked mechanically, never the arbiter
of whether a number is right.

> Asserted by `test_a_generous_judge_cannot_outvote_a_deterministic_check`.

With no vendor credentials the judge falls back to a deterministic rubric scorer, and the
report is marked `judge_is_mock: true` so nobody mistakes a structural heuristic for
semantic judgement.

---

## 5. Dimensions

Sixteen, with default weights in `finagent_evaluation/scoring.py`:

| Dimension | Weight | Measures |
| --- | --- | --- |
| `factual_accuracy` | 0.18 | Claims that survive verification |
| `numerical_accuracy` | 0.13 | Figures that match the source or recompute correctly |
| `hallucination_resistance` | 0.13 | Absence of unsupported assertion |
| `citation_accuracy` | 0.11 | Citations that point at evidence containing the claim |
| `financial_reasoning` | 0.09 | Structure: thesis, assumptions, risks, disconfirming evidence |
| `citation_completeness` | 0.07 | Claims that carry a citation at all |
| `instruction_adherence` | 0.05 | Required output fields present |
| `historical_validity` | 0.05 | No evidence from after the cutoff |
| `statistical_validity` | 0.04 | Sample sizes, multiple-comparison discipline |
| `robustness` | 0.03 | Stability under rephrasing |
| `reproducibility` | 0.03 | Agreement across repeated identical runs |
| `overfitting_risk` | 0.02 | Train-to-test degradation on attached backtests |
| `tool_use_efficiency` | 0.02 | Steps relative to the work required |
| `cost_efficiency` | 0.02 | Cost relative to the configured budget |
| `investment_usefulness` | 0.02 | Actionability of the conclusion |
| `latency` | 0.01 | Wall-clock time |

**Unmeasured dimensions are excluded, and the remaining weights are renormalised.** A
dimension nobody could measure is not scored zero — that would punish an agent for the
evaluator's blind spot. Excluded dimensions are listed on the report.

> Asserted by `test_unmeasured_dimensions_are_excluded_and_weights_renormalised`.

---

## 6. The golden dataset

`FINANCIAL_RESEARCH_BASIC_V1` — 25 cases with known answers derived from the seeded ACME
Technologies corpus. Case categories: financial statements, ratio analysis, growth
analysis, segment analysis, risk identification, guidance, historical reasoning and
unanswerable questions.

Three case shapes do most of the work:

- **Numeric cases** carry `expected_value`, a `unit` and an acceptable band. Getting the
  number wrong fails; *not answering* also fails, because silence is not correctness.
- **Historical cases** carry an `information_cutoff` and name `forbidden_sources` — the
  documents the agent must not use. `ACME_FY2022_GROSS_MARGIN_HISTORICAL` sets a mid-2023
  cutoff and forbids the FY2023 10-K, earnings release and call.
- **Unanswerable cases** (`ACME_UNKNOWABLE_FY2025`) have no expected value. The correct
  answer is a refusal. Confidently answering is the failure.

A suite declares its own dimension weights, so a numerical-accuracy suite and a reasoning
suite can score the same agent differently and honestly.

> Asserted by `test_the_golden_dataset_is_well_formed`.

---

## 7. What a score is, and is not

> This is an agent-quality score measuring evidence grounding, citation accuracy,
> numerical correctness and instruction adherence. It does not predict investment returns
> and must not be used as a return forecast.

That sentence is attached to every evaluation detail response and rendered on every
evaluation page. Leaderboards rank on quality dimensions and cost efficiency, never on
investment return.

---

## 8. Reading a failure

Each failure carries a code, a title, a human-readable reason, the expected and actual
values, a severity, and the dimension it affected. A failure is meant to be actionable:
`CLAIM_UNSUPPORTED` with the claim text and the evidence that was available tells you
whether to fix the prompt, the tool set or the corpus.

---

## 9. Proving the evaluators work

A measurement system that passes everything is useless. The demo workspace seeds a second
agent, `mock-analyst-weak`, which deliberately omits citations and asserts a growth figure
its evidence does not support.

On the standard ACME question the two agents score roughly **98** and **58**: the flawed
fixture's fabricated claim is caught as `CLAIM_UNSUPPORTED`, its citation coverage is 0%,
and its hallucination rate is non-zero. That gap is the evidence that the evaluators
discriminate rather than merely penalise.

> Asserted by `test_unsupported_financial_claim_is_flagged` and
> `test_well_behaved_agent_scores_above_the_flawed_fixture`.
