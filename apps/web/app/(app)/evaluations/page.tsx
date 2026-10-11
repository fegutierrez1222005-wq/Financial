import Link from "next/link";
import type { Metadata } from "next";

import { ActionForm } from "@/components/action-form";
import {
  Badge,
  EmptyState,
  Notice,
  PageHeader,
  Panel,
  ScoreBar,
  StatusBadge,
} from "@/components/primitives";
import { runSuite } from "@/app/(app)/actions";
import { apiFetchOrNull } from "@/lib/api";
import { formatDateTime, formatPercent, formatRatioAsPercent } from "@/lib/format";
import type { Agent, Evaluation } from "@/lib/types";

export const metadata: Metadata = { title: "Evaluations" };

type Suite = {
  key: string;
  name: string;
  description: string | null;
  version: string;
  is_builtin: boolean;
  case_count: number;
  dataset_note: string | null;
  weights: Record<string, number>;
};

export default async function EvaluationsPage() {
  const [suites, agents, evaluations] = await Promise.all([
    apiFetchOrNull<Suite[]>("/evaluations/suites"),
    apiFetchOrNull<Agent[]>("/agents"),
    apiFetchOrNull<Evaluation[]>("/evaluations?limit=40"),
  ]);

  return (
    <>
      <PageHeader
        title="Evaluations"
        subtitle="Claims are extracted deterministically and checked against the evidence the agent retrieved. Deterministic and programmatic checks carry the weight; an LLM judge contributes a fraction and can never outvote them."
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_1.5fr]">
        <div className="space-y-4">
          <Panel title="Run a suite">
            <div className="p-4">
              <ActionForm action={runSuite} submitLabel="Run suite" pendingLabel="Running cases…">
                <div className="space-y-4">
                  <div>
                    <label className="field-label" htmlFor="suite_key">
                      Suite
                    </label>
                    <select id="suite_key" name="suite_key" required className="field-input">
                      {(suites ?? []).map((suite) => (
                        <option key={suite.key} value={suite.key}>
                          {suite.name} ({suite.case_count} cases)
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="field-label" htmlFor="agent_id">
                      Agent
                    </label>
                    <select id="agent_id" name="agent_id" required className="field-input">
                      {(agents ?? []).map((agent) => (
                        <option key={agent.id} value={agent.id}>
                          {agent.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="field-label" htmlFor="max_cases">
                      Limit to first N cases
                    </label>
                    <input
                      id="max_cases"
                      name="max_cases"
                      type="number"
                      min="1"
                      className="field-input numeric"
                      placeholder="all"
                    />
                    <p className="field-hint">
                      Each case is a full agent run, so a whole suite costs real money against a
                      vendor model.
                    </p>
                  </div>
                </div>
              </ActionForm>
            </div>
          </Panel>

          <Panel title="Golden datasets">
            {!suites || suites.length === 0 ? (
              <EmptyState title="No suites installed" description="Built-in suites install on first use." />
            ) : (
              <ul className="divide-y divide-ink-800">
                {suites.map((suite) => (
                  <li key={suite.key} className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Link
                        href={`/evaluations/suites/${suite.key}`}
                        className="text-sm text-ink-100"
                      >
                        {suite.name}
                      </Link>
                      {suite.is_builtin ? <Badge>Built-in</Badge> : null}
                      <span className="numeric ml-auto text-2xs text-ink-400">
                        {suite.case_count} cases
                      </span>
                    </div>
                    {suite.description ? (
                      <p className="mt-1 text-2xs leading-relaxed text-ink-400">
                        {suite.description}
                      </p>
                    ) : null}
                    {suite.dataset_note ? (
                      <p className="mt-1.5 text-2xs leading-relaxed text-ink-500">
                        {suite.dataset_note}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Notice tone="caution">
            A score measures research process quality — evidence grounding, citation accuracy,
            numerical correctness, instruction adherence. It does not predict investment returns.
          </Notice>
        </div>

        <Panel title="Evaluation history">
          {!evaluations || evaluations.length === 0 ? (
            <EmptyState
              title="Nothing scored yet"
              description="Score an individual run from its page, or run a whole suite against an agent."
            />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Score</th>
                  <th>Kind</th>
                  <th>Status</th>
                  <th>Cases</th>
                  <th>Pass rate</th>
                  <th>Hallucination</th>
                  <th>Judge</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {evaluations.map((evaluation) => (
                  <tr key={evaluation.id}>
                    <td>
                      <Link href={`/evaluations/${evaluation.id}`} className="block">
                        <ScoreBar value={evaluation.overall_score} />
                      </Link>
                    </td>
                    <td>
                      <Badge tone={evaluation.kind === "suite" ? "info" : "neutral"}>
                        {evaluation.kind}
                      </Badge>
                      {evaluation.suite_key ? (
                        <div className="mt-1 font-mono text-2xs text-ink-500">
                          {evaluation.suite_key}
                        </div>
                      ) : null}
                    </td>
                    <td>
                      <StatusBadge status={evaluation.status} />
                    </td>
                    <td className="numeric">
                      {evaluation.case_count === null
                        ? "—"
                        : `${evaluation.passed_count ?? 0}/${evaluation.case_count}`}
                    </td>
                    <td className="numeric">{formatPercent(evaluation.pass_rate)}</td>
                    <td className="numeric">
                      {formatRatioAsPercent(evaluation.hallucination_rate)}
                    </td>
                    <td>
                      {evaluation.judge_is_mock ? (
                        <Badge tone="mock">Deterministic</Badge>
                      ) : (
                        <span className="font-mono text-2xs">{evaluation.judge_model}</span>
                      )}
                    </td>
                    <td className="text-2xs text-ink-400">
                      {formatDateTime(evaluation.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </>
  );
}
