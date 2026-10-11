import Link from "next/link";
import type { Metadata } from "next";

import { ActionForm } from "@/components/action-form";
import {
  EmptyState,
  Notice,
  PageHeader,
  Panel,
  ProvenanceBadges,
  StatusBadge,
} from "@/components/primitives";
import { ResearchTaskFields, type TaskTemplate } from "@/components/research-task-fields";
import { startResearchRun } from "@/app/(app)/actions";
import { apiFetchOrNull } from "@/lib/api";
import { formatDateTime, formatDuration, formatRatioAsPercent, formatUsd } from "@/lib/format";
import type { Agent, ResearchRun } from "@/lib/types";

export const metadata: Metadata = { title: "Research" };

export default async function ResearchPage({
  searchParams,
}: {
  searchParams: Promise<{ agent?: string }>;
}) {
  const { agent: preselected } = await searchParams;
  const [agents, templates, runs, suites] = await Promise.all([
    apiFetchOrNull<Agent[]>("/agents"),
    apiFetchOrNull<TaskTemplate[]>("/research/templates"),
    apiFetchOrNull<ResearchRun[]>("/research/runs?limit=30"),
    apiFetchOrNull<Array<{ key: string; name: string }>>("/evaluations/suites"),
  ]);

  return (
    <>
      <PageHeader
        title="Research"
        subtitle="Give an agent a question. Every retrieval, tool call and model call is recorded so the answer can be reviewed rather than trusted."
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <Panel title="New research run">
          <div className="p-4">
            <ActionForm
              action={startResearchRun}
              submitLabel="Run research"
              pendingLabel="Running…"
            >
              <div className="space-y-4">
                <div>
                  <label className="field-label" htmlFor="agent_id">
                    Agent
                  </label>
                  <select
                    id="agent_id"
                    name="agent_id"
                    required
                    className="field-input"
                    defaultValue={preselected ?? (agents ?? [])[0]?.id}
                  >
                    {(agents ?? []).map((agent) => (
                      <option key={agent.id} value={agent.id}>
                        {agent.name}
                      </option>
                    ))}
                  </select>
                </div>

                <ResearchTaskFields templates={templates ?? []} />

                <div>
                  <label className="field-label" htmlFor="information_cutoff">
                    Information cutoff
                  </label>
                  <input
                    id="information_cutoff"
                    name="information_cutoff"
                    type="date"
                    className="field-input numeric"
                  />
                  <p className="field-hint">
                    Restricts the agent to information published on or before this date. Enforced
                    in the query, not by asking the model. Evidence with an unknown publication
                    date is excluded.
                  </p>
                </div>

                <div>
                  <label className="field-label" htmlFor="evaluation_suite_key">
                    Score against
                  </label>
                  <select
                    id="evaluation_suite_key"
                    name="evaluation_suite_key"
                    className="field-input"
                    defaultValue=""
                  >
                    <option value="">No suite</option>
                    {(suites ?? []).map((suite) => (
                      <option key={suite.key} value={suite.key}>
                        {suite.name}
                      </option>
                    ))}
                  </select>
                </div>

                <Notice tone="caution">
                  A run costs money when a vendor model is configured. Cost is estimated from the
                  rate card and recorded against the run.
                </Notice>
              </div>
            </ActionForm>
          </div>
        </Panel>

        <Panel title="Runs">
          {!runs || runs.length === 0 ? (
            <EmptyState
              title="No runs yet"
              description="Start one on the left. Debate sub-runs are grouped under their parent and do not appear here."
            />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Model</th>
                  <th>Evidence</th>
                  <th>Citations</th>
                  <th>Cost</th>
                  <th>Duration</th>
                  <th>Started</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td>
                      <Link
                        href={`/research/runs/${run.id}`}
                        className="font-mono text-2xs text-ink-100"
                      >
                        {run.id.slice(0, 8)}
                      </Link>
                      <div className="mt-1">
                        <ProvenanceBadges
                          usedMockModel={run.used_mock_model}
                          usedDemoData={run.used_demo_data}
                        />
                      </div>
                    </td>
                    <td>
                      <StatusBadge status={run.status} />
                      {run.information_cutoff ? (
                        <div className="mt-1 text-2xs text-ink-500">as-of restricted</div>
                      ) : null}
                    </td>
                    <td className="font-mono text-2xs">{run.model}</td>
                    <td className="numeric">{run.evidence_count}</td>
                    <td className="numeric">{formatRatioAsPercent(run.citation_coverage)}</td>
                    <td className="numeric">{formatUsd(run.estimated_cost_usd)}</td>
                    <td className="numeric">{formatDuration(run.duration_ms)}</td>
                    <td className="text-2xs text-ink-400">{formatDateTime(run.created_at)}</td>
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
