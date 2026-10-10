import Link from "next/link";
import type { Metadata } from "next";

import {
  Badge,
  EmptyState,
  Notice,
  PageHeader,
  Panel,
  ScoreBar,
} from "@/components/primitives";
import { apiFetchOrNull } from "@/lib/api";
import { formatDateTime, formatPercent, formatRatioAsPercent, titleCase } from "@/lib/format";
import type { ScoreboardEntry } from "@/lib/types";

export const metadata: Metadata = { title: "Leaderboard" };

export default async function LeaderboardPage() {
  const [scoreboard, modelComparison] = await Promise.all([
    apiFetchOrNull<ScoreboardEntry[]>("/evaluations/scoreboard"),
    apiFetchOrNull<{ rows: Array<Record<string, unknown>>; ranking_basis: string }>(
      "/comparisons/models",
    ),
  ]);

  const dimensions = Array.from(
    new Set((scoreboard ?? []).flatMap((entry) => Object.keys(entry.dimension_scores))),
  ).slice(0, 6);

  return (
    <>
      <PageHeader
        title="Leaderboard"
        subtitle="The latest suite result for each agent version in this workspace."
      />

      <div className="mb-4">
        <Notice tone="caution">
          Ranked on agent-quality dimensions — factual accuracy, citation accuracy, numerical
          accuracy, hallucination resistance and cost efficiency. Never on investment return, and
          never as a prediction of one.
        </Notice>
      </div>

      <Panel title="Agent versions">
        {!scoreboard || scoreboard.length === 0 ? (
          <EmptyState
            title="Nothing ranked yet"
            description="Run an evaluation suite against an agent and it will appear here."
            action={
              <Link href="/evaluations" className="button-primary no-underline">
                Run a suite
              </Link>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Agent</th>
                  <th>Model</th>
                  <th>Overall</th>
                  <th>Pass rate</th>
                  <th>Hallucination</th>
                  <th>Citations</th>
                  {dimensions.map((dimension) => (
                    <th key={dimension}>{titleCase(dimension)}</th>
                  ))}
                  <th>Evaluated</th>
                </tr>
              </thead>
              <tbody>
                {scoreboard.map((entry) => (
                  <tr key={entry.evaluation_id}>
                    <td className="numeric text-ink-500">{entry.rank}</td>
                    <td>
                      <Link href={`/agents/${entry.agent_id}`} className="text-ink-100">
                        {entry.agent_name}
                      </Link>
                      <div className="mt-0.5 text-2xs text-ink-500">v{entry.version_number}</div>
                    </td>
                    <td className="font-mono text-2xs">
                      {entry.model}
                      {entry.judge_is_mock ? (
                        <span className="ml-1.5">
                          <Badge tone="mock">Deterministic judge</Badge>
                        </span>
                      ) : null}
                    </td>
                    <td>
                      <Link href={`/evaluations/${entry.evaluation_id}`} className="block">
                        <ScoreBar value={entry.overall_score} />
                      </Link>
                    </td>
                    <td className="numeric">{formatPercent(entry.pass_rate)}</td>
                    <td className="numeric">{formatRatioAsPercent(entry.hallucination_rate)}</td>
                    <td className="numeric">{formatRatioAsPercent(entry.citation_coverage)}</td>
                    {dimensions.map((dimension) => (
                      <td key={dimension} className="numeric">
                        {entry.dimension_scores[dimension]?.toFixed(0) ?? "—"}
                      </td>
                    ))}
                    <td className="text-2xs text-ink-400">{formatDateTime(entry.evaluated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <div className="mt-4">
        <Panel
          title="Model comparison"
          description="Aggregated across every suite evaluation in this workspace."
        >
          {!modelComparison || modelComparison.rows.length === 0 ? (
            <EmptyState
              title="Not enough data"
              description="Run the same suite against two different models to compare them."
            />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  {Object.keys(modelComparison.rows[0]).map((column) => (
                    <th key={column}>{titleCase(column)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {modelComparison.rows.map((row, index) => (
                  <tr key={index}>
                    {Object.entries(row).map(([column, value]) => (
                      <td key={column} className={typeof value === "number" ? "numeric" : ""}>
                        {typeof value === "number" ? value.toFixed(2) : String(value ?? "—")}
                      </td>
                    ))}
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
