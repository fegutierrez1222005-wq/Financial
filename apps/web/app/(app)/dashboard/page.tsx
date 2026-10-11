import Link from "next/link";
import type { Metadata } from "next";

import {
  EmptyState,
  Metric,
  Notice,
  PageHeader,
  Panel,
  ScoreBar,
  StatusBadge,
} from "@/components/primitives";
import { apiFetchOrNull } from "@/lib/api";
import { EMPTY, formatDateTime, formatDuration, formatUsd, formatPercent } from "@/lib/format";
import type { Dashboard } from "@/lib/types";

export const metadata: Metadata = { title: "Dashboard" };

export default async function DashboardPage() {
  const dashboard = await apiFetchOrNull<Dashboard>("/dashboard?days=30");

  if (!dashboard) {
    return (
      <Panel>
        <EmptyState
          title="The dashboard is unavailable"
          description="The API did not return workspace metrics. Check that the service is reachable and try again."
        />
      </Panel>
    );
  }

  const headline = dashboard.headline;
  const usage = dashboard.usage as {
    unit_economics?: Record<string, number | string | null>;
    totals?: Record<string, number>;
  };
  const economics = usage?.unit_economics ?? {};

  return (
    <>
      <PageHeader
        title="Workspace overview"
        subtitle="Agent quality, cost and activity over the last 30 days."
      />

      <div className="grid gap-4 lg:grid-cols-4">
        <Panel title="Activity" className="lg:col-span-2">
          <div className="grid grid-cols-2 divide-x divide-ink-800 sm:grid-cols-4">
            <Metric label="Agents" value={headline.total_agents ?? 0} />
            <Metric label="Runs (30d)" value={headline.runs_in_window ?? 0} />
            <Metric
              label="Failed runs"
              value={headline.failed_runs_in_window ?? 0}
              tone={headline.failed_runs_in_window ? "negative" : "neutral"}
            />
            <Metric label="Evaluations" value={headline.evaluations_in_window ?? 0} />
          </div>
        </Panel>

        <Panel title="Quality" className="lg:col-span-2">
          <div className="grid grid-cols-2 divide-x divide-ink-800 sm:grid-cols-4">
            <Metric
              label="Mean score"
              value={headline.mean_evaluation_score?.toFixed(1) ?? EMPTY}
              hint="Agent quality, not return"
            />
            <Metric label="Pass rate" value={formatPercent(headline.mean_pass_rate)} />
            <Metric
              label="Citation coverage"
              value={formatPercent(headline.mean_citation_coverage)}
              tone={headline.mean_citation_coverage >= 80 ? "positive" : "caution"}
            />
            <Metric
              label="Hallucination rate"
              value={formatPercent(headline.mean_hallucination_rate)}
              tone={headline.mean_hallucination_rate > 5 ? "negative" : "positive"}
            />
          </div>
        </Panel>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Panel title="Unit economics" description="Estimated from the configured rate card.">
          <dl className="divide-y divide-ink-800">
            <div className="flex items-baseline justify-between px-4 py-2.5">
              <dt className="text-2xs uppercase tracking-[0.1em] text-ink-400">Cost per run</dt>
              <dd className="numeric text-sm">
                {formatUsd(Number(economics.cost_per_run_usd ?? 0))}
              </dd>
            </div>
            <div className="flex items-baseline justify-between px-4 py-2.5">
              <dt className="text-2xs uppercase tracking-[0.1em] text-ink-400">
                Per successful run
              </dt>
              <dd className="numeric text-sm">
                {economics.cost_per_successful_run_usd === null
                  ? EMPTY
                  : formatUsd(Number(economics.cost_per_successful_run_usd))}
              </dd>
            </div>
            <div className="flex items-baseline justify-between px-4 py-2.5">
              <dt className="text-2xs uppercase tracking-[0.1em] text-ink-400">
                Per accurate answer
              </dt>
              <dd className="numeric text-sm">
                {economics.cost_per_accurate_answer_usd === null
                  ? EMPTY
                  : formatUsd(Number(economics.cost_per_accurate_answer_usd))}
              </dd>
            </div>
            <div className="flex items-baseline justify-between px-4 py-2.5">
              <dt className="text-2xs uppercase tracking-[0.1em] text-ink-400">Mean duration</dt>
              <dd className="numeric text-sm">{formatDuration(headline.mean_duration_ms)}</dd>
            </div>
          </dl>
          <div className="px-4 pb-4">
            <Notice tone="caution">
              “Accurate answer” means an evaluation scored at or above the quality threshold. It
              does not mean the market agreed.
            </Notice>
          </div>
        </Panel>

        <Panel title="Agent performance" className="lg:col-span-2">
          {dashboard.agent_performance.length === 0 ? (
            <EmptyState
              title="No agents have run yet"
              description="Create an agent and give it a research task to populate this table."
              action={
                <Link href="/agents" className="button-primary no-underline">
                  Go to agents
                </Link>
              }
            />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Agent</th>
                  <th>Runs</th>
                  <th>Mean score</th>
                  <th>Mean cost</th>
                  <th>Mean duration</th>
                </tr>
              </thead>
              <tbody>
                {dashboard.agent_performance.map((agent) => (
                  <tr key={agent.agent_id}>
                    <td>
                      <Link href={`/agents/${agent.agent_id}`} className="text-ink-100">
                        {agent.agent_name}
                      </Link>
                    </td>
                    <td className="numeric">{agent.runs}</td>
                    <td>
                      <ScoreBar value={agent.mean_score} />
                    </td>
                    <td className="numeric">{formatUsd(agent.mean_cost_usd)}</td>
                    <td className="numeric">{formatDuration(agent.mean_duration_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Panel title="Recent runs">
          {dashboard.recent_runs.length === 0 ? (
            <EmptyState title="No runs yet" description="Research runs will appear here." />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Model</th>
                  <th>Cost</th>
                  <th>Started</th>
                </tr>
              </thead>
              <tbody>
                {dashboard.recent_runs.map((run) => {
                  const record = run as Record<string, string | number | boolean | null>;
                  return (
                    <tr key={String(record.id)}>
                      <td>
                        <Link
                          href={`/research/runs/${record.id}`}
                          className="font-mono text-2xs text-ink-200"
                        >
                          {String(record.id).slice(0, 8)}
                        </Link>
                      </td>
                      <td>
                        <StatusBadge status={String(record.status)} />
                      </td>
                      <td className="font-mono text-2xs">{String(record.model)}</td>
                      <td className="numeric">{formatUsd(Number(record.estimated_cost_usd))}</td>
                      <td className="text-2xs text-ink-400">
                        {formatDateTime(String(record.created_at))}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel
          title="Recent failure modes"
          description="What the evaluators caught, newest first."
        >
          {dashboard.evaluation_failures.length === 0 ? (
            <EmptyState
              title="No recorded failures"
              description="Failures appear here once evaluations have run against your agents."
            />
          ) : (
            <ul className="divide-y divide-ink-800">
              {dashboard.evaluation_failures.slice(0, 8).map((failure, index) => (
                <li key={`${failure.evaluation_id}-${index}`} className="px-4 py-3">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-sm text-ink-100">{failure.title ?? failure.code}</span>
                    <span className="font-mono text-2xs text-ink-500">{failure.dimension}</span>
                  </div>
                  <p className="mt-1 text-2xs leading-relaxed text-ink-400">{failure.reason}</p>
                  {failure.run_id ? (
                    <Link
                      href={`/research/runs/${failure.run_id}`}
                      className="mt-1.5 inline-block text-2xs text-signal-info"
                    >
                      Inspect the run
                    </Link>
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
