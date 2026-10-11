import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { ActionForm } from "@/components/action-form";
import {
  Badge,
  DefinitionRow,
  EmptyState,
  Notice,
  PageHeader,
  Panel,
  StatusBadge,
} from "@/components/primitives";
import { publishAgentVersion } from "@/app/(app)/actions";
import { apiFetchOrNull } from "@/lib/api";
import { formatDateTime, formatUsd } from "@/lib/format";
import type { Agent, AgentVersion, ModelDescriptor, ResearchRun, ToolDescriptor } from "@/lib/types";

export const metadata: Metadata = { title: "Agent" };

export default async function AgentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const agent = await apiFetchOrNull<Agent>(`/agents/${id}`);
  if (!agent) notFound();

  const [versions, prompts, tools, models, runs] = await Promise.all([
    apiFetchOrNull<AgentVersion[]>(`/agents/${id}/versions`),
    apiFetchOrNull<Array<{ id: string; version_number: number; content: string; created_at: string }>>(
      `/agents/${id}/prompts`,
    ),
    apiFetchOrNull<ToolDescriptor[]>("/catalog/tools"),
    apiFetchOrNull<ModelDescriptor[]>("/catalog/models"),
    apiFetchOrNull<ResearchRun[]>(`/research/runs?agent_id=${id}&limit=10`),
  ]);

  const current = agent.current_version;
  const availableModels = (models ?? []).filter((model) => model.available);
  const currentPrompt = (prompts ?? []).find(
    (prompt) => prompt.id === current?.prompt_version_id,
  );

  return (
    <>
      <PageHeader
        title={agent.name}
        subtitle={agent.description ?? undefined}
        action={
          <Link href={`/research?agent=${agent.id}`} className="button-primary no-underline">
            Run research
          </Link>
        }
      />

      {agent.is_demo ? (
        <div className="mb-4">
          <Notice tone="mock">
            This is a seeded demo agent operating on the fictional ACME Technologies corpus.
          </Notice>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
        <div className="space-y-4">
          <Panel title={`Current version — v${current?.version_number ?? 1}`}>
            <dl>
              <DefinitionRow term="Model">{current?.model}</DefinitionRow>
              <DefinitionRow term="Temperature">{current?.temperature}</DefinitionRow>
              <DefinitionRow term="Max steps">{current?.max_steps}</DefinitionRow>
              <DefinitionRow term="Timeout">{current?.timeout_seconds}s</DefinitionRow>
              <DefinitionRow term="Output format">{current?.output_format}</DefinitionRow>
              <DefinitionRow term="Config hash">
                <span className="font-mono text-2xs">{current?.config_hash.slice(0, 16)}</span>
              </DefinitionRow>
              <DefinitionRow term="Published">{formatDateTime(current?.created_at)}</DefinitionRow>
            </dl>
            <div className="border-t border-ink-800 px-4 py-3">
              <div className="panel-title mb-2">Tools</div>
              <div className="flex flex-wrap gap-1.5">
                {(current?.tools ?? []).map((tool) => (
                  <Badge key={tool}>{tool}</Badge>
                ))}
                {current?.tools.length === 0 ? (
                  <span className="text-2xs text-ink-500">No tools enabled.</span>
                ) : null}
              </div>
            </div>
          </Panel>

          <Panel title="Version history" description="Agents are never edited in place.">
            <table className="data-table">
              <thead>
                <tr>
                  <th>v</th>
                  <th>Model</th>
                  <th>Change</th>
                  <th>Published</th>
                </tr>
              </thead>
              <tbody>
                {(versions ?? []).map((version) => (
                  <tr key={version.id}>
                    <td className="numeric">{version.version_number}</td>
                    <td className="font-mono text-2xs">{version.model}</td>
                    <td className="text-2xs text-ink-400">{version.change_note ?? "—"}</td>
                    <td className="text-2xs text-ink-400">{formatDateTime(version.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          <Panel title="Recent runs">
            {!runs || runs.length === 0 ? (
              <EmptyState
                title="This agent has not run yet"
                description="Give it a research task to see its trace, evidence and score."
              />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Run</th>
                    <th>Status</th>
                    <th>Cost</th>
                    <th>Started</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.id}>
                      <td>
                        <Link
                          href={`/research/runs/${run.id}`}
                          className="font-mono text-2xs text-ink-200"
                        >
                          {run.id.slice(0, 8)}
                        </Link>
                      </td>
                      <td>
                        <StatusBadge status={run.status} />
                      </td>
                      <td className="numeric">{formatUsd(run.estimated_cost_usd)}</td>
                      <td className="text-2xs text-ink-400">{formatDateTime(run.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </div>

        <Panel
          title="Publish a new version"
          description="Changing the configuration creates v{next}; past runs keep pointing at the version that produced them."
        >
          <div className="p-4">
            <ActionForm
              action={publishAgentVersion}
              submitLabel="Publish new version"
              pendingLabel="Publishing…"
            >
              <input type="hidden" name="agent_id" value={agent.id} />
              <div className="space-y-4">
                <div>
                  <label className="field-label" htmlFor="name">
                    Name
                  </label>
                  <input
                    id="name"
                    name="name"
                    required
                    defaultValue={agent.name}
                    className="field-input"
                  />
                </div>
                <div>
                  <label className="field-label" htmlFor="description">
                    Description
                  </label>
                  <input
                    id="description"
                    name="description"
                    defaultValue={agent.description ?? ""}
                    className="field-input"
                  />
                </div>
                <div>
                  <label className="field-label" htmlFor="model">
                    Model
                  </label>
                  <select
                    id="model"
                    name="model"
                    className="field-input"
                    defaultValue={current?.model ?? ""}
                  >
                    <option value="">Best available</option>
                    {availableModels.map((model) => (
                      <option key={model.key} value={model.key}>
                        {model.display_name}
                        {model.is_mock ? " — simulated" : ""}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <span className="field-label">Tools</span>
                  <div className="space-y-1.5 rounded border border-ink-700 p-3">
                    {(tools ?? []).map((tool) => (
                      <label key={tool.name} className="flex items-center gap-2.5 text-sm text-ink-300">
                        <input
                          type="checkbox"
                          name="tools"
                          value={tool.name}
                          defaultChecked={current?.tools.includes(tool.name)}
                          disabled={!tool.available}
                          className="h-4 w-4"
                        />
                        <span className="font-mono text-2xs">{tool.name}</span>
                        <span className="text-2xs text-ink-500">{tool.title}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="field-label" htmlFor="instructions">
                    Instructions
                  </label>
                  <textarea
                    id="instructions"
                    name="instructions"
                    rows={10}
                    defaultValue={currentPrompt?.content ?? ""}
                    className="field-input font-mono text-2xs"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="field-label" htmlFor="temperature">
                      Temperature
                    </label>
                    <input
                      id="temperature"
                      name="temperature"
                      type="number"
                      step="0.1"
                      min="0"
                      max="2"
                      defaultValue={current?.temperature ?? 0.2}
                      className="field-input numeric"
                    />
                  </div>
                  <div>
                    <label className="field-label" htmlFor="max_steps">
                      Max steps
                    </label>
                    <input
                      id="max_steps"
                      name="max_steps"
                      type="number"
                      min="1"
                      max="30"
                      defaultValue={current?.max_steps ?? 8}
                      className="field-input numeric"
                    />
                  </div>
                </div>
                <div>
                  <label className="field-label" htmlFor="output_format">
                    Output format
                  </label>
                  <select
                    id="output_format"
                    name="output_format"
                    className="field-input"
                    defaultValue={current?.output_format ?? "markdown"}
                  >
                    <option value="markdown">Markdown report</option>
                    <option value="investment_thesis">Structured investment thesis</option>
                    <option value="json">JSON</option>
                  </select>
                </div>
                <div>
                  <label className="field-label" htmlFor="change_note">
                    What changed
                  </label>
                  <input
                    id="change_note"
                    name="change_note"
                    className="field-input"
                    placeholder="Recorded on the version so a reviewer can see why"
                  />
                </div>
              </div>
            </ActionForm>
          </div>
        </Panel>
      </div>
    </>
  );
}
