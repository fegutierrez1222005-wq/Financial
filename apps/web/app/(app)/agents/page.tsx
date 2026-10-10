import Link from "next/link";
import type { Metadata } from "next";

import { ActionForm } from "@/components/action-form";
import { Badge, EmptyState, Notice, PageHeader, Panel } from "@/components/primitives";
import { createAgent } from "@/app/(app)/actions";
import { apiFetchOrNull } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { Agent, ModelDescriptor, ToolDescriptor } from "@/lib/types";

export const metadata: Metadata = { title: "Agents" };

export default async function AgentsPage() {
  const [agents, tools, models] = await Promise.all([
    apiFetchOrNull<Agent[]>("/agents"),
    apiFetchOrNull<ToolDescriptor[]>("/catalog/tools"),
    apiFetchOrNull<ModelDescriptor[]>("/catalog/models"),
  ]);

  const availableModels = (models ?? []).filter((model) => model.available);
  const unavailableModels = (models ?? []).filter((model) => !model.available);

  return (
    <>
      <PageHeader
        title="Agents"
        subtitle="An agent is a model, a set of instructions, a tool allow-list and the data it may read. Every change publishes a new immutable version."
      />

      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <Panel title="Your agents">
          {!agents || agents.length === 0 ? (
            <EmptyState
              title="No agents yet"
              description="Create one with the form beside this panel. It will be usable immediately."
            />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Model</th>
                  <th>Tools</th>
                  <th>Versions</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((agent) => (
                  <tr key={agent.id}>
                    <td>
                      <Link href={`/agents/${agent.id}`} className="text-ink-100">
                        {agent.name}
                      </Link>
                      {agent.is_demo ? (
                        <span className="ml-2">
                          <Badge tone="mock">Demo</Badge>
                        </span>
                      ) : null}
                      {agent.description ? (
                        <p className="mt-1 max-w-md text-2xs leading-relaxed text-ink-400">
                          {agent.description}
                        </p>
                      ) : null}
                    </td>
                    <td className="font-mono text-2xs">{agent.current_version?.model ?? "—"}</td>
                    <td className="text-2xs text-ink-400">
                      {agent.current_version?.tools.join(", ") || "none"}
                    </td>
                    <td className="numeric">{agent.version_count}</td>
                    <td className="text-2xs text-ink-400">{formatDateTime(agent.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="New agent">
          <div className="p-4">
            <ActionForm action={createAgent} submitLabel="Create agent" pendingLabel="Creating…">
              <div className="space-y-4">
                <div>
                  <label className="field-label" htmlFor="name">
                    Name
                  </label>
                  <input id="name" name="name" required className="field-input" />
                </div>

                <div>
                  <label className="field-label" htmlFor="description">
                    Description
                  </label>
                  <input id="description" name="description" className="field-input" />
                </div>

                <div>
                  <label className="field-label" htmlFor="model">
                    Model
                  </label>
                  <select id="model" name="model" className="field-input" defaultValue="">
                    <option value="">Best available</option>
                    {availableModels.map((model) => (
                      <option key={model.key} value={model.key}>
                        {model.display_name}
                        {model.is_mock ? " — simulated" : ""}
                      </option>
                    ))}
                  </select>
                  {unavailableModels.length > 0 ? (
                    <p className="field-hint">
                      {unavailableModels.length} model(s) are hidden because their provider has no
                      credentials in this deployment.
                    </p>
                  ) : null}
                </div>

                <div>
                  <span className="field-label">Tools</span>
                  <div className="space-y-1.5 rounded border border-ink-700 p-3">
                    {(tools ?? []).map((tool) => (
                      <label
                        key={tool.name}
                        className="flex items-start gap-2.5 text-sm text-ink-300"
                      >
                        <input
                          type="checkbox"
                          name="tools"
                          value={tool.name}
                          defaultChecked={tool.name === "DOCUMENT_SEARCH"}
                          disabled={!tool.available}
                          className="mt-0.5 h-4 w-4"
                        />
                        <span>
                          <span className="text-ink-200">{tool.title}</span>
                          <span className="ml-1.5 font-mono text-2xs text-ink-500">
                            {tool.name}
                          </span>
                          <span className="mt-0.5 block text-2xs leading-snug text-ink-500">
                            {tool.available
                              ? tool.description
                              : `Unavailable: ${tool.unavailable_reason}`}
                          </span>
                        </span>
                      </label>
                    ))}
                  </div>
                  <p className="field-hint">
                    An agent can only call tools on this list. Asking for anything else is refused
                    at execution time.
                  </p>
                </div>

                <div>
                  <label className="field-label" htmlFor="instructions">
                    Instructions
                  </label>
                  <textarea
                    id="instructions"
                    name="instructions"
                    rows={5}
                    className="field-input font-mono text-2xs"
                    placeholder="Leave blank to use the institutional research default."
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
                      defaultValue="0.2"
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
                      defaultValue="8"
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
                    defaultValue="markdown"
                  >
                    <option value="markdown">Markdown report</option>
                    <option value="investment_thesis">Structured investment thesis</option>
                    <option value="json">JSON</option>
                  </select>
                </div>

                <Notice tone="info">
                  Temperature above zero makes a run harder to reproduce. The reproducibility
                  dimension measures this directly rather than assuming it.
                </Notice>
              </div>
            </ActionForm>
          </div>
        </Panel>
      </div>
    </>
  );
}
