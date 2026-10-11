import Link from "next/link";

import { Badge } from "@/components/primitives";

const PROBLEMS = [
  {
    title: "You cannot tell whether the answer is right",
    body:
      "A model will produce a confident paragraph about a company's margins whether or not the " +
      "filing says so. Without claim-level verification against retrieved source text, a wrong " +
      "answer and a right one look identical.",
  },
  {
    title: "You cannot tell what it actually did",
    body:
      "A result with no trace is not research. Every retrieval, tool call, calculation and model " +
      "call has to be recorded, in order, with latency and cost, or the work cannot be reviewed.",
  },
  {
    title: "Historical tests quietly use future information",
    body:
      "Ask an agent what it would have concluded in June 2023 and it will happily read the " +
      "annual report filed in February 2024. Unless the cutoff is enforced structurally, every " +
      "historical evaluation is contaminated.",
  },
  {
    title: "A backtest proves whatever you want it to",
    body:
      "Trade on the bar that generated the signal, ignore costs, reuse the out-of-sample window " +
      "twenty times, and any strategy looks good. The assumptions have to be reported with the result.",
  },
];

const CAPABILITIES = [
  {
    name: "Agent builder",
    body:
      "Model, instructions, tool allow-list and data bindings. Every change publishes a new " +
      "immutable version with its own configuration hash, so a past run is always tied to the " +
      "exact configuration that produced it.",
  },
  {
    name: "Full execution trace",
    body:
      "Plan, retrievals, tool calls, model calls, tokens, latency and estimated cost — recorded " +
      "step by step and replayable.",
  },
  {
    name: "Claim-level verification",
    body:
      "The output is decomposed into typed claims — factual, forward-looking, assumption, " +
      "unknown — and each one is checked against the evidence the agent actually retrieved. " +
      "Deterministic, so the same output always scores the same.",
  },
  {
    name: "Golden dataset and scoring",
    body:
      "Twenty-five curated cases with known answers. Deterministic and programmatic checks carry " +
      "the weight; an LLM judge contributes a fraction and can never outvote them.",
  },
  {
    name: "Information cutoff",
    body:
      "Lock a run to what was public on a date. Enforced in the query and in the data providers, " +
      "not by asking the model nicely. Evidence with an unknown publication date is excluded.",
  },
  {
    name: "Backtesting with stated assumptions",
    body:
      "Commissions, slippage and a one-bar execution lag by default. Train, validation and " +
      "out-of-sample windows are reported separately and never averaged.",
  },
  {
    name: "Experiments and benchmarks",
    body:
      "Change one variable — model, prompt version, tool set — and compare on a fixed case set, " +
      "with the platform telling you when a gap is inside run-to-run noise.",
  },
  {
    name: "Cost and quality observability",
    body:
      "Cost per run, per successful run and per accurate answer, alongside hallucination rate " +
      "and citation coverage over time.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-ink-950">
      <header className="border-b border-ink-800">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <span className="font-mono text-sm font-semibold tracking-[0.2em] text-ink-100">
            FINAGENT&nbsp;LAB
          </span>
          <nav className="flex items-center gap-3 text-sm">
            <Link href="/login" className="text-ink-300 no-underline hover:text-ink-100">
              Sign in
            </Link>
            <Link href="/register" className="button-primary no-underline">
              Create an account
            </Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="border-b border-ink-800">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <Badge tone="info">Evaluation &amp; observability layer</Badge>
            <h1 className="mt-5 max-w-3xl text-4xl font-semibold leading-[1.1] tracking-tight text-ink-100">
              Know whether your financial AI is actually right.
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-relaxed text-ink-300">
              FINAGENT LAB is the measurement layer for institutional financial research agents.
              Build an agent, run it against filings and market data, capture every action it
              takes, verify every claim against the evidence it retrieved, and score it against a
              golden dataset with known answers.
            </p>
            <p className="mt-4 max-w-2xl text-sm leading-relaxed text-ink-400">
              For hedge funds, asset managers, family offices and quant researchers who need an
              audit trail, not a chat transcript.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/register" className="button-primary no-underline">
                Start with the demo workspace
              </Link>
              <Link href="/login" className="button-secondary no-underline">
                Sign in
              </Link>
            </div>
            <p className="mt-6 max-w-2xl text-2xs leading-relaxed text-ink-500">
              The demo workspace contains ACME Technologies, a fictional issuer with synthetic
              filings and prices. It is labelled as demo data everywhere it appears and exists so
              you can see the full pipeline work before connecting your own documents.
            </p>
          </div>
        </section>

        <section className="border-b border-ink-800">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <h2 className="text-2xs font-semibold uppercase tracking-[0.16em] text-ink-400">
              The problem
            </h2>
            <div className="mt-8 grid gap-px overflow-hidden rounded border border-ink-800 bg-ink-800 md:grid-cols-2">
              {PROBLEMS.map((problem) => (
                <article key={problem.title} className="bg-ink-900 p-6">
                  <h3 className="text-sm font-semibold text-ink-100">{problem.title}</h3>
                  <p className="mt-2.5 text-sm leading-relaxed text-ink-400">{problem.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="border-b border-ink-800">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <h2 className="text-2xs font-semibold uppercase tracking-[0.16em] text-ink-400">
              What the platform does
            </h2>
            <div className="mt-8 grid gap-px overflow-hidden rounded border border-ink-800 bg-ink-800 md:grid-cols-2 lg:grid-cols-4">
              {CAPABILITIES.map((capability) => (
                <article key={capability.name} className="bg-ink-900 p-5">
                  <h3 className="text-sm font-semibold text-ink-100">{capability.name}</h3>
                  <p className="mt-2 text-2xs leading-relaxed text-ink-400">{capability.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="border-b border-ink-800">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <h2 className="text-2xs font-semibold uppercase tracking-[0.16em] text-ink-400">
              What this platform will not do
            </h2>
            <ul className="mt-6 max-w-3xl space-y-3 text-sm leading-relaxed text-ink-300">
              <li>
                <span className="text-ink-100">It does not predict returns.</span> A score measures
                research process quality — evidence grounding, citation accuracy, numerical
                correctness. It is not a forecast and must not be used as one.
              </li>
              <li>
                <span className="text-ink-100">It does not give investment advice.</span> It is a
                tool for professional research teams to measure their own agents.
              </li>
              <li>
                <span className="text-ink-100">It does not trade.</span> There is no live execution
                path, by design.
              </li>
              <li>
                <span className="text-ink-100">It does not present simulated output as real.</span>{" "}
                Anything produced by a deterministic local provider or the demo corpus is labelled
                wherever it appears.
              </li>
              <li>
                <span className="text-ink-100">It does not train on your data.</span> Customer data
                is isolated and is not used for model training unless explicitly authorized.
              </li>
            </ul>
          </div>
        </section>

        <section>
          <div className="mx-auto max-w-6xl px-6 py-16">
            <h2 className="text-lg font-semibold tracking-tight text-ink-100">
              See the whole loop in one session
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-400">
              Sign up and the demo workspace is seeded for you: an indexed corpus, a working
              analyst agent, a deliberately flawed fixture agent so you can watch the evaluators
              catch a fabricated claim, a 25-case golden dataset, and a backtest over synthetic
              prices.
            </p>
            <Link href="/register" className="button-primary mt-7 no-underline">
              Create an account
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-ink-800">
        <div className="mx-auto max-w-6xl px-6 py-8 text-2xs leading-relaxed text-ink-500">
          <p>
            FINAGENT LAB is research tooling for professional investment teams. Nothing produced by
            this platform is investment advice, and no score or simulation predicts future returns.
          </p>
          <p className="mt-2">
            Customer data is isolated and is not used for model training unless explicitly
            authorized.
          </p>
        </div>
      </footer>
    </div>
  );
}
