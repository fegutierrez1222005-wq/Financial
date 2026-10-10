import Link from "next/link";
import type { Metadata } from "next";

import { ActionForm } from "@/components/action-form";
import { EmptyState, Notice, PageHeader, Panel, StatusBadge } from "@/components/primitives";
import { createExperiment } from "@/app/(app)/actions";
import { apiFetchOrNull } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { Agent } from "@/lib/types";

export const metadata: Metadata = { title: "Experiments" };

type Experiment = {
  id: string;
  name: string;
  variable: string;
  suite_key: string | null;
  status: string;
  conclusion: string | null;
  created_at: string;
  arms: Array<{ arm_label: string; overall_score: number | null }>;
};

export default async function ExperimentsPage() {
  const [experiments, agents, suites] = await Promise.all([
    apiFetchOrNull<Experiment[]>("/experiments"),
    apiFetchOrNull<Agent[]>("/agents"),
    apiFetchOrNull<Array<{ key: string; name: string }>>("/evaluations/suites"),
  ]);

  const agentOptions = agents ?? [];

  return (
    <>
      <PageHeader
        title="Experiments"
        subtitle="Change exactly one thing — the model, the prompt version, the tool set — and measure both arms on the same cases."
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_1.3fr]">
        <Panel title="New experiment">
          <div className="p-4">
            <ActionForm
              action={createExperiment}
              submitLabel="Create experiment"
              pendingLabel="Creating…"
            >
              <div className="space-y-4">
                <div>
                  <label className="field-label" htmlFor="name">
                    Name
                  </label>
                  <input id="name" name="name" required className="field-input" />
                </div>
                <div>
                  <label className="field-label" htmlFor="hypothesis">
                    Hypothesis
                  </label>
                  <input
                    id="hypothesis"
                    name="hypothesis"
                    className="field-input"
                    placeholder="Stating it up front is what stops the result being rationalised afterwards."
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="field-label" htmlFor="variable">
                      Variable
                    </label>
                    <select
                      id="variable"
                      name="variable"
                      className="field-input"
                      defaultValue="agent_version"
                    >
                      <option value="model">Model</option>
                      <option value="prompt_version">Prompt version</option>
                      <option value="agent_version">Agent version</option>
                      <option value="tools">Tools</option>
                    </select>
                  </div>
                  <div>
                    <label className="field-label" htmlFor="suite_key">
                      Suite
                    </label>
                    <select id="suite_key" name="suite_key" required className="field-input">
                      {(suites ?? []).map((suite) => (
                        <option key={suite.key} value={suite.key}>
                          {suite.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {(["a", "b"] as const).map((arm, index) => (
                  <fieldset key={arm} className="rounded border border-ink-700 p-3">
                    <legend className="px-1 text-2xs uppercase tracking-[0.12em] text-ink-400">
                      Arm {arm.toUpperCase()}
                    </legend>
                    <div className="space-y-3">
                      <div>
                        <label className="field-label" htmlFor={`arm_${arm}_label`}>
                          Label
                        </label>
                        <input
                          id={`arm_${arm}_label`}
                          name={`arm_${arm}_label`}
                          className="field-input"
                          defaultValue={arm === "a" ? "control" : "variant"}
                        />
                      </div>
                      <div>
                        <label className="field-label" htmlFor={`arm_${arm}_agent_id`}>
                          Agent
                        </label>
                        <select
                          id={`arm_${arm}_agent_id`}
                          name={`arm_${arm}_agent_id`}
                          required
                          className="field-input"
                          defaultValue={agentOptions[index]?.id ?? agentOptions[0]?.id}
                        >
                          {agentOptions.map((agent) => (
                            <option key={agent.id} value={agent.id}>
                              {agent.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </fieldset>
                ))}

                <div>
                  <label className="field-label" htmlFor="max_cases">
                    Limit to first N cases
                  </label>
                  <input
                    id="max_cases"
                    name="max_cases"
                    type="number"
                    min="1"
                    defaultValue="5"
                    className="field-input numeric"
                  />
                  <p className="field-hint">
                    Every case runs once per arm, so an experiment costs roughly arms × cases runs.
                  </p>
                </div>

                <Notice tone="caution">
                  A gap of less than two points on a small case set is inside run-to-run noise.
                  The conclusion will say so rather than declaring a winner.
                </Notice>
              </div>
            </ActionForm>
          </div>
        </Panel>

        <Panel title="Experiments">
          {!experiments || experiments.length === 0 ? (
            <EmptyState
              title="No experiments yet"
              description="Create one to compare two configurations on identical cases."
            />
          ) : (
            <ul className="divide-y divide-ink-800">
              {experiments.map((experiment) => (
                <li key={experiment.id} className="px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={`/experiments/${experiment.id}`}
                      className="text-sm text-ink-100"
                    >
                      {experiment.name}
                    </Link>
                    <StatusBadge status={experiment.status} />
                    <span className="ml-auto text-2xs text-ink-500">
                      {formatDateTime(experiment.created_at)}
                    </span>
                  </div>
                  <p className="mt-1 text-2xs text-ink-500">
                    Variable: {experiment.variable} · Suite: {experiment.suite_key}
                  </p>
                  {experiment.conclusion ? (
                    <p className="mt-1.5 text-2xs leading-relaxed text-ink-400">
                      {experiment.conclusion}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  );
}
