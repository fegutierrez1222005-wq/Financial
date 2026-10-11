import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { SubmitButton } from "@/components/action-form";
import {
  EmptyState,
  Notice,
  PageHeader,
  Panel,
  ScoreBar,
  StatusBadge,
} from "@/components/primitives";
import { AutoRefresh } from "@/components/auto-refresh";
import { runExperiment } from "@/app/(app)/actions";
import { apiFetchOrNull } from "@/lib/api";
import { EMPTY, formatDuration, formatPercent, formatRatioAsPercent, formatUsd } from "@/lib/format";

export const metadata: Metadata = { title: "Experiment" };

type Experiment = {
  id: string;
  name: string;
  hypothesis: string | null;
  variable: string;
  suite_key: string | null;
  status: string;
  conclusion: string | null;
  results_summary: {
    winner?: string | null;
    conclusion?: string;
    caveat?: string;
  };
  arms: Array<{
    id: string;
    arm_label: string;
    model: string | null;
    status: string;
    overall_score: number | null;
    pass_rate: number | null;
    hallucination_rate: number | null;
    citation_coverage: number | null;
    total_cost_usd: number | null;
    total_tokens: number | null;
    mean_latency_ms: number | null;
    error_message: string | null;
  }>;
};

export default async function ExperimentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const experiment = await apiFetchOrNull<Experiment>(`/experiments/${id}`);
  if (!experiment) notFound();

  const summary = experiment.results_summary ?? {};

  return (
    <>
      <PageHeader
        title={experiment.name}
        subtitle={experiment.hypothesis ?? undefined}
        action={
          <form action={runExperiment}>
            <input type="hidden" name="experiment_id" value={experiment.id} />
            <SubmitButton
              label={experiment.status === "SUCCEEDED" ? "Run again" : "Run experiment"}
              pendingLabel="Running every arm…"
            />
          </form>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <StatusBadge status={experiment.status} />
        <span className="text-2xs text-ink-500">
          Variable: {experiment.variable} · Suite: {experiment.suite_key}
        </span>
      </div>

      <div className="mb-4 empty:hidden">
        <AutoRefresh status={experiment.status} label="experiment" />
      </div>

      {experiment.conclusion ? (
        <div className="mb-4">
          <Notice tone={summary.winner ? "info" : "caution"}>{experiment.conclusion}</Notice>
        </div>
      ) : null}

      <Panel title="Arms">
        {experiment.arms.length === 0 ? (
          <EmptyState title="No arms" description="This experiment has no configured arms." />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Arm</th>
                <th>Status</th>
                <th>Model</th>
                <th>Overall</th>
                <th>Pass rate</th>
                <th>Hallucination</th>
                <th>Citations</th>
                <th>Cost</th>
                <th>Mean latency</th>
              </tr>
            </thead>
            <tbody>
              {experiment.arms.map((arm) => (
                <tr key={arm.id}>
                  <td className="text-ink-100">
                    {arm.arm_label}
                    {summary.winner === arm.arm_label ? (
                      <span className="ml-2 text-2xs text-signal-positive">best</span>
                    ) : null}
                  </td>
                  <td>
                    <StatusBadge status={arm.status} />
                    {arm.error_message ? (
                      <div className="mt-1 text-2xs text-signal-negative">{arm.error_message}</div>
                    ) : null}
                  </td>
                  <td className="font-mono text-2xs">{arm.model ?? EMPTY}</td>
                  <td>
                    <ScoreBar value={arm.overall_score} />
                  </td>
                  <td className="numeric">{formatPercent(arm.pass_rate)}</td>
                  <td className="numeric">{formatRatioAsPercent(arm.hallucination_rate)}</td>
                  <td className="numeric">{formatRatioAsPercent(arm.citation_coverage)}</td>
                  <td className="numeric">{formatUsd(arm.total_cost_usd)}</td>
                  <td className="numeric">{formatDuration(arm.mean_latency_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {summary.caveat ? (
        <div className="mt-4">
          <Notice tone="caution">{summary.caveat}</Notice>
        </div>
      ) : null}
    </>
  );
}
