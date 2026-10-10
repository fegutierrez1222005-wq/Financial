import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";

import {
  Badge,
  EmptyState,
  Metric,
  Notice,
  PageHeader,
  Panel,
  ScoreBar,
  StatusBadge,
} from "@/components/primitives";
import { apiFetchOrNull } from "@/lib/api";
import {
  EMPTY,
  formatDuration,
  formatPercent,
  formatRatioAsPercent,
  titleCase,
} from "@/lib/format";
import type { EvaluationDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Evaluation" };

const SUPPORT_TONE: Record<string, "positive" | "caution" | "negative" | "neutral"> = {
  DIRECTLY_SUPPORTED: "positive",
  PARTIALLY_SUPPORTED: "caution",
  INFERRED: "caution",
  ASSUMED: "neutral",
  UNKNOWN: "neutral",
  UNSUPPORTED: "negative",
  CONTRADICTED: "negative",
};

const SEVERITY_TONE: Record<string, "negative" | "caution" | "neutral"> = {
  BLOCKING: "negative",
  ERROR: "negative",
  WARNING: "caution",
  INFO: "neutral",
};

export default async function EvaluationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const detail = await apiFetchOrNull<EvaluationDetail>(`/evaluations/${id}`);
  if (!detail) notFound();

  const { evaluation } = detail;
  const failures = detail.results.filter((result) => !result.passed);

  return (
    <>
      <PageHeader
        title={evaluation.kind === "suite" ? `Suite: ${evaluation.suite_key}` : "Run evaluation"}
        subtitle={detail.score_interpretation}
        action={
          evaluation.run_id ? (
            <Link
              href={`/research/runs/${evaluation.run_id}`}
              className="button-secondary no-underline"
            >
              Open the run
            </Link>
          ) : undefined
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <StatusBadge status={evaluation.status} />
        {evaluation.judge_is_mock ? (
          <Badge tone="mock" title="No vendor judge credentials are configured.">
            Deterministic judge
          </Badge>
        ) : (
          <Badge tone="info">Judge: {evaluation.judge_model}</Badge>
        )}
      </div>

      {evaluation.error_message ? (
        <div className="mb-4">
          <Notice tone="negative">
            {evaluation.error_code}: {evaluation.error_message}
          </Notice>
        </div>
      ) : null}

      <Panel className="mb-4">
        <div className="grid grid-cols-2 divide-x divide-ink-800 md:grid-cols-6">
          <Metric
            label="Overall"
            value={evaluation.overall_score?.toFixed(1) ?? EMPTY}
            hint="Agent quality"
          />
          <Metric label="Pass rate" value={formatPercent(evaluation.pass_rate)} />
          <Metric
            label="Cases"
            value={
              evaluation.case_count === null
                ? EMPTY
                : `${evaluation.passed_count ?? 0}/${evaluation.case_count}`
            }
          />
          <Metric
            label="Hallucination"
            value={formatRatioAsPercent(evaluation.hallucination_rate)}
            tone={evaluation.hallucination_rate ? "negative" : "positive"}
          />
          <Metric
            label="Citation coverage"
            value={formatRatioAsPercent(evaluation.citation_coverage)}
          />
          <Metric label="Duration" value={formatDuration(evaluation.duration_ms)} />
        </div>
      </Panel>

      {evaluation.warnings.length > 0 ? (
        <div className="mb-4 space-y-2">
          {evaluation.warnings.map((warning) => (
            <Notice key={warning} tone="caution">
              {warning}
            </Notice>
          ))}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <Panel
          title="Dimensions"
          description="Unmeasured dimensions are excluded and the remaining weights are renormalised."
        >
          <table className="data-table">
            <thead>
              <tr>
                <th>Dimension</th>
                <th>Score</th>
                <th>Weight</th>
              </tr>
            </thead>
            <tbody>
              {detail.scores.map((score) => (
                <tr key={score.dimension}>
                  <td>{titleCase(score.dimension)}</td>
                  <td>
                    <ScoreBar value={score.score} />
                  </td>
                  <td className="numeric">{(score.weight * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <div className="space-y-4">
          <Panel
            title={`Failures (${failures.length})`}
            description="What the evaluators caught, worst first."
          >
            {failures.length === 0 ? (
              <EmptyState
                title="No failures"
                description="Every check the evaluators could apply passed. Dimensions that could not be measured are listed as excluded rather than scored."
              />
            ) : (
              <ul className="divide-y divide-ink-800">
                {failures.map((failure, index) => (
                  <li key={`${failure.failure_code}-${index}`} className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm text-ink-100">
                        {failure.failure_title ?? failure.failure_code}
                      </span>
                      <Badge tone={SEVERITY_TONE[failure.severity ?? "INFO"] ?? "neutral"}>
                        {failure.severity ?? "INFO"}
                      </Badge>
                      {failure.case_key ? (
                        <span className="font-mono text-2xs text-ink-500">{failure.case_key}</span>
                      ) : null}
                    </div>
                    <p className="mt-1.5 text-2xs leading-relaxed text-ink-400">
                      {failure.failure_reason}
                    </p>
                    {failure.expected || failure.actual ? (
                      <dl className="mt-2 grid grid-cols-2 gap-3 font-mono text-2xs">
                        <div>
                          <dt className="text-ink-500">expected</dt>
                          <dd className="text-ink-200">{failure.expected ?? EMPTY}</dd>
                        </div>
                        <div>
                          <dt className="text-ink-500">actual</dt>
                          <dd className="text-signal-negative">{failure.actual ?? EMPTY}</dd>
                        </div>
                      </dl>
                    ) : null}
                    {failure.run_id ? (
                      <Link
                        href={`/research/runs/${failure.run_id}`}
                        className="mt-2 inline-block text-2xs text-signal-info"
                      >
                        Inspect the run
                      </Link>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          {detail.claims.length > 0 ? (
            <Panel
              title={`Claims (${detail.claims.length})`}
              description="Every assertion in the output, typed and checked against the retrieved evidence."
            >
              <ul className="divide-y divide-ink-800">
                {detail.claims.map((claim, index) => (
                  <li key={index} className="px-4 py-3">
                    <div className="flex items-start gap-3">
                      <span className="flex-1 text-sm leading-relaxed text-ink-200">
                        {claim.text}
                      </span>
                      <Badge tone={SUPPORT_TONE[claim.support_level ?? "UNKNOWN"] ?? "neutral"}>
                        {(claim.support_level ?? "UNKNOWN").replace(/_/g, " ")}
                      </Badge>
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2 text-2xs text-ink-500">
                      <span>{claim.kind}</span>
                      {claim.section ? <span>· {claim.section}</span> : null}
                      {claim.similarity !== null ? (
                        <span className="numeric">· similarity {claim.similarity.toFixed(2)}</span>
                      ) : null}
                    </div>
                    {claim.explanation ? (
                      <p className="mt-1.5 text-2xs leading-relaxed text-ink-400">
                        {claim.explanation}
                      </p>
                    ) : null}
                    {claim.evidence_quote ? (
                      <blockquote className="mt-2 border-l-2 border-ink-600 pl-3 font-mono text-2xs leading-relaxed text-ink-500">
                        {claim.evidence_quote.slice(0, 320)}
                      </blockquote>
                    ) : null}
                  </li>
                ))}
              </ul>
            </Panel>
          ) : null}
        </div>
      </div>
    </>
  );
}
