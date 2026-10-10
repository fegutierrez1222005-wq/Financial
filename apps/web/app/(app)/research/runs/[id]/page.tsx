import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { SubmitButton } from "@/components/action-form";
import {
  Badge,
  DefinitionRow,
  EmptyState,
  Metric,
  Notice,
  PageHeader,
  Panel,
  ProvenanceBadges,
  StatusBadge,
} from "@/components/primitives";
import { evaluateRun, reproduceRun, runDebate } from "@/app/(app)/actions";
import { apiFetchOrNull } from "@/lib/api";
import {
  EMPTY,
  formatDateTime,
  formatDuration,
  formatRatioAsPercent,
  formatUsd,
  titleCase,
} from "@/lib/format";
import type { RunDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Run" };

const SUPPORT_TONE: Record<string, "positive" | "caution" | "negative" | "neutral"> = {
  DIRECTLY_SUPPORTED: "positive",
  PARTIALLY_SUPPORTED: "caution",
  INFERRED: "caution",
  ASSUMED: "neutral",
  UNKNOWN: "neutral",
  UNSUPPORTED: "negative",
  CONTRADICTED: "negative",
};

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const detail = await apiFetchOrNull<RunDetail>(`/research/runs/${id}`);
  if (!detail) notFound();

  const { run, task } = detail;

  return (
    <>
      <PageHeader
        title={task?.title ?? "Research run"}
        subtitle={task?.question}
        action={
          <div className="flex flex-wrap gap-2">
            <form action={evaluateRun}>
              <input type="hidden" name="run_id" value={run.id} />
              <SubmitButton label="Evaluate" pendingLabel="Scoring…" />
            </form>
            <form action={reproduceRun}>
              <input type="hidden" name="run_id" value={run.id} />
              <SubmitButton label="Reproduce" pendingLabel="Re-running…" variant="secondary" />
            </form>
            <form action={runDebate}>
              <input type="hidden" name="run_id" value={run.id} />
              <SubmitButton label="Debate" pendingLabel="Debating…" variant="secondary" />
            </form>
          </div>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <StatusBadge status={run.status} />
        <ProvenanceBadges usedMockModel={run.used_mock_model} usedDemoData={run.used_demo_data} />
        {run.information_cutoff ? (
          <Badge tone="info" title="The agent could only read evidence published on or before this instant.">
            As-of {formatDateTime(run.information_cutoff)}
          </Badge>
        ) : (
          <Badge>Live information</Badge>
        )}
        {run.debate_role ? <Badge tone="info">{run.debate_role}</Badge> : null}
      </div>

      {run.error_message ? (
        <div className="mb-4">
          <Notice tone="negative">
            {run.error_code}: {run.error_message}
          </Notice>
        </div>
      ) : null}

      {run.warnings.length > 0 ? (
        <div className="mb-4 space-y-2">
          {run.warnings.map((warning) => (
            <Notice key={warning} tone="caution">
              {warning}
            </Notice>
          ))}
        </div>
      ) : null}

      <Panel className="mb-4">
        <div className="grid grid-cols-2 divide-x divide-ink-800 md:grid-cols-6">
          <Metric label="Evidence" value={run.evidence_count} />
          <Metric
            label="Citation coverage"
            value={
              run.citation_coverage === null
                ? "not scored"
                : formatRatioAsPercent(run.citation_coverage)
            }
            hint={
              run.citation_coverage === null
                ? "Run an evaluation to measure this"
                : "Claims with a source"
            }
          />
          <Metric
            label="Hallucination"
            value={
              run.hallucination_rate === null
                ? "not scored"
                : formatRatioAsPercent(run.hallucination_rate)
            }
            hint={run.hallucination_rate === null ? "Run an evaluation to measure this" : undefined}
            tone={run.hallucination_rate ? "negative" : "neutral"}
          />
          <Metric label="Tool calls" value={run.tool_call_count} />
          <Metric
            label="Tokens"
            value={(run.input_tokens + run.output_tokens).toLocaleString("en-US")}
          />
          <Metric
            label="Cost"
            value={formatUsd(run.estimated_cost_usd)}
            hint="Estimated"
          />
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-4">
          <Panel title="Output">
            {run.output_text ? (
              <pre className="whitespace-pre-wrap px-4 py-4 font-mono text-2xs leading-relaxed text-ink-200">
                {run.output_text}
              </pre>
            ) : (
              <EmptyState
                title="No output"
                description="This run did not produce a report. The trace below shows how far it got."
              />
            )}
          </Panel>

          <Panel
            title="Execution trace"
            description="Every action, in order, with its latency and cost."
          >
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Step</th>
                  <th>Action</th>
                  <th>Latency</th>
                  <th>Tokens</th>
                  <th>Cost</th>
                </tr>
              </thead>
              <tbody>
                {detail.trace.map((step) => (
                  <tr key={step.sequence}>
                    <td className="numeric text-ink-500">{step.sequence}</td>
                    <td>
                      <Badge tone={step.error_code ? "negative" : "neutral"}>{step.kind}</Badge>
                      {step.tool_name ? (
                        <div className="mt-1 font-mono text-2xs text-ink-400">{step.tool_name}</div>
                      ) : null}
                      {step.model ? (
                        <div className="mt-1 font-mono text-2xs text-ink-400">{step.model}</div>
                      ) : null}
                    </td>
                    <td className="max-w-md text-2xs leading-relaxed text-ink-300">
                      {step.action}
                      {step.error_message ? (
                        <div className="mt-1 text-signal-negative">{step.error_message}</div>
                      ) : null}
                    </td>
                    <td className="numeric">{formatDuration(step.latency_ms)}</td>
                    <td className="numeric">
                      {step.input_tokens || step.output_tokens
                        ? `${step.input_tokens ?? 0}/${step.output_tokens ?? 0}`
                        : EMPTY}
                    </td>
                    <td className="numeric">{formatUsd(step.estimated_cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          <Panel
            title="Evidence"
            description="The exact text the agent retrieved. Each item is a citable unit."
          >
            {detail.evidence.length === 0 ? (
              <EmptyState
                title="No evidence retrieved"
                description="Nothing in the indexed corpus was admissible for this question under the active information cutoff."
              />
            ) : (
              <ul className="divide-y divide-ink-800">
                {detail.evidence.map((item) => (
                  <li key={item.chunk_ref} className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm text-ink-100">{item.document_name}</span>
                      {item.page_number ? (
                        <span className="text-2xs text-ink-500">page {item.page_number}</span>
                      ) : null}
                      {item.is_demo ? <Badge tone="mock">Demo</Badge> : null}
                      <span className="ml-auto font-mono text-2xs text-ink-500">
                        {item.publication_timestamp
                          ? formatDateTime(item.publication_timestamp)
                          : "publication date unknown"}
                      </span>
                    </div>
                    <p className="mt-2 font-mono text-2xs leading-relaxed text-ink-400">
                      {item.text.slice(0, 600)}
                      {item.text.length > 600 ? "…" : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="Run record">
            <dl>
              <DefinitionRow term="Status">{run.status}</DefinitionRow>
              <DefinitionRow term="Model">{run.model}</DefinitionRow>
              <DefinitionRow term="Duration">{formatDuration(run.duration_ms)}</DefinitionRow>
              <DefinitionRow term="Model calls">{run.model_calls}</DefinitionRow>
              <DefinitionRow term="Confidence">
                {run.confidence === null ? EMPTY : `${(run.confidence * 100).toFixed(0)}%`}
              </DefinitionRow>
              <DefinitionRow term="Started">{formatDateTime(run.started_at)}</DefinitionRow>
              <DefinitionRow term="Reproducibility key">
                <span className="font-mono text-2xs">
                  {run.reproducibility_key?.slice(0, 16) ?? EMPTY}
                </span>
              </DefinitionRow>
            </dl>
            {run.reproduced_from_run_id ? (
              <div className="border-t border-ink-800 px-4 py-3 text-2xs text-ink-400">
                Reproduced from{" "}
                <Link
                  href={`/research/runs/${run.reproduced_from_run_id}`}
                  className="text-signal-info"
                >
                  {run.reproduced_from_run_id.slice(0, 8)}
                </Link>
              </div>
            ) : null}
          </Panel>

          <Panel title="Plan">
            {detail.plan.length === 0 ? (
              <EmptyState title="No plan recorded" description="This run produced no plan steps." />
            ) : (
              <ol className="divide-y divide-ink-800">
                {detail.plan.map((step) => (
                  <li key={step.step_index} className="flex items-baseline gap-3 px-4 py-2.5">
                    <span className="numeric text-2xs text-ink-500">{step.step_index + 1}</span>
                    <span className="flex-1 text-sm text-ink-200">{step.title}</span>
                    <Badge tone={step.status === "FAILED" ? "negative" : "neutral"}>
                      {titleCase(step.kind)}
                    </Badge>
                  </li>
                ))}
              </ol>
            )}
          </Panel>

          <Panel title="Tool calls">
            {detail.tool_calls.length === 0 ? (
              <EmptyState title="No tools used" description="This run answered without calling a tool." />
            ) : (
              <ul className="divide-y divide-ink-800">
                {detail.tool_calls.map((call, index) => (
                  <li key={`${call.tool_name}-${index}`} className="px-4 py-2.5">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-mono text-2xs text-ink-200">{call.tool_name}</span>
                      <Badge tone={call.status === "SUCCEEDED" ? "positive" : "negative"}>
                        {call.status}
                      </Badge>
                    </div>
                    <p className="mt-1 font-mono text-2xs leading-snug text-ink-500">
                      {JSON.stringify(call.arguments).slice(0, 180)}
                    </p>
                    {call.error_message ? (
                      <p className="mt-1 text-2xs text-signal-negative">{call.error_message}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Evaluations">
            {detail.evaluations.length === 0 ? (
              <EmptyState
                title="Not scored yet"
                description="Use Evaluate above to verify every claim against the retrieved evidence."
              />
            ) : (
              <ul className="divide-y divide-ink-800">
                {detail.evaluations.map((evaluation) => (
                  <li
                    key={evaluation.id}
                    className="flex items-center justify-between gap-3 px-4 py-2.5"
                  >
                    <Link
                      href={`/evaluations/${evaluation.id}`}
                      className="text-sm text-ink-200"
                    >
                      {evaluation.overall_score?.toFixed(1) ?? EMPTY} overall
                    </Link>
                    <StatusBadge status={evaluation.status} />
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          {detail.citations.length > 0 ? (
            <Panel title="Verified citations">
              <ul className="divide-y divide-ink-800">
                {detail.citations.slice(0, 12).map((citation, index) => {
                  const record = citation as Record<string, string | number | null>;
                  const support = String(record.support_level ?? "UNKNOWN");
                  return (
                    <li key={index} className="px-4 py-2.5">
                      <div className="flex items-start justify-between gap-3">
                        <span className="flex-1 text-2xs leading-relaxed text-ink-300">
                          {String(record.claim_text ?? "").slice(0, 200)}
                        </span>
                        <Badge tone={SUPPORT_TONE[support] ?? "neutral"}>
                          {support.replace(/_/g, " ")}
                        </Badge>
                      </div>
                      <p className="mt-1 text-2xs text-ink-500">
                        {record.document_name}
                        {record.page_number ? `, page ${record.page_number}` : ""}
                      </p>
                    </li>
                  );
                })}
              </ul>
            </Panel>
          ) : null}
        </div>
      </div>
    </>
  );
}
