import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { Badge, EmptyState, Notice, PageHeader, Panel } from "@/components/primitives";
import { apiFetchOrNull } from "@/lib/api";
import { EMPTY, formatDate } from "@/lib/format";

export const metadata: Metadata = { title: "Golden dataset" };

type Case = {
  id: string;
  key: string;
  question: string;
  expected_answer: string | null;
  expected_value: number | null;
  unit: string | null;
  acceptable_low: number | null;
  acceptable_high: number | null;
  required_sources: string[];
  forbidden_sources: string[];
  required_fields: string[];
  difficulty: string | null;
  category: string | null;
  evaluation_method: string | null;
  information_cutoff: string | null;
  notes: string | null;
};

export default async function SuitePage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const cases = await apiFetchOrNull<Case[]>(`/evaluations/suites/${key}/cases`);
  if (!cases) notFound();

  const historical = cases.filter((item) => item.information_cutoff);

  return (
    <>
      <PageHeader
        title={key}
        subtitle="Each case has a known answer derived from the indexed corpus, so a result is a fact about the agent rather than an opinion about it."
      />

      <div className="mb-4 grid gap-3 md:grid-cols-3">
        <Notice tone="info">
          {cases.length} cases. {historical.length} of them impose an information cutoff and name
          the sources the agent must not use.
        </Notice>
        <Notice tone="caution">
          Cases with no expected value test whether the agent correctly declines to answer.
          Confidently answering an unanswerable question is a failure.
        </Notice>
        <Notice tone="mock">
          Cases marked demo-dependent are answerable only against the seeded ACME Technologies
          corpus.
        </Notice>
      </div>

      <Panel title="Cases">
        {cases.length === 0 ? (
          <EmptyState title="This suite has no cases" description="Nothing to show." />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Key</th>
                <th>Question</th>
                <th>Expected</th>
                <th>Tolerance</th>
                <th>Cutoff</th>
                <th>Method</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((item) => (
                <tr key={item.id}>
                  <td className="font-mono text-2xs text-ink-300">{item.key}</td>
                  <td className="max-w-md text-2xs leading-relaxed">
                    {item.question}
                    {item.forbidden_sources.length > 0 ? (
                      <p className="mt-1 text-2xs text-signal-caution">
                        Must not use: {item.forbidden_sources.join(", ")}
                      </p>
                    ) : null}
                    {item.notes ? (
                      <p className="mt-1 text-2xs text-ink-500">{item.notes}</p>
                    ) : null}
                  </td>
                  <td className="numeric text-2xs">
                    {item.expected_value === null
                      ? item.expected_answer ?? EMPTY
                      : `${item.expected_value} ${item.unit ?? ""}`}
                  </td>
                  <td className="numeric text-2xs text-ink-400">
                    {item.acceptable_low === null || item.acceptable_high === null
                      ? EMPTY
                      : `${item.acceptable_low} – ${item.acceptable_high}`}
                  </td>
                  <td className="text-2xs">
                    {item.information_cutoff ? (
                      <Badge tone="info">{formatDate(item.information_cutoff)}</Badge>
                    ) : (
                      EMPTY
                    )}
                  </td>
                  <td className="text-2xs text-ink-400">{item.evaluation_method}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </>
  );
}
