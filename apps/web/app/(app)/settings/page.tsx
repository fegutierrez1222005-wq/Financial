import type { Metadata } from "next";

import {
  Badge,
  DefinitionRow,
  EmptyState,
  Notice,
  PageHeader,
  Panel,
} from "@/components/primitives";
import { apiFetchOrNull } from "@/lib/api";
import { formatDateTime, formatUsd, titleCase } from "@/lib/format";
import type { ProviderStatus, Workspace } from "@/lib/types";

export const metadata: Metadata = { title: "Settings" };

type Member = {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  created_at: string;
};

type ApiKey = {
  id: string;
  name: string;
  key_prefix: string;
  role: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

type AuditEntry = {
  id: string;
  action: string;
  resource_type: string | null;
  outcome: string;
  created_at: string;
};

type Usage = {
  period_start?: string;
  period_end?: string;
  totals?: Record<string, number>;
  unit_economics?: Record<string, number | string | null>;
  by_model?: Array<Record<string, string | number>>;
  plan?: Record<string, string | number | null>;
};

export default async function SettingsPage() {
  const [workspace, members, keys, usage, audit, providers] = await Promise.all([
    apiFetchOrNull<Workspace>("/workspaces/current"),
    apiFetchOrNull<Member[]>("/workspaces/current/members"),
    apiFetchOrNull<ApiKey[]>("/workspaces/current/api-keys"),
    apiFetchOrNull<Usage>("/usage?days=30"),
    apiFetchOrNull<AuditEntry[]>("/audit-logs?limit=25"),
    apiFetchOrNull<ProviderStatus>("/providers/status"),
  ]);

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Workspace, members, automation credentials, usage and the audit trail."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Workspace">
          {workspace ? (
            <dl>
              <DefinitionRow term="Name">{workspace.name}</DefinitionRow>
              <DefinitionRow term="Slug">
                <span className="font-mono text-2xs">{workspace.slug}</span>
              </DefinitionRow>
              <DefinitionRow term="Your role">{workspace.role}</DefinitionRow>
              <DefinitionRow term="Default cutoff">
                {workspace.default_information_cutoff
                  ? formatDateTime(workspace.default_information_cutoff)
                  : "none (live information)"}
              </DefinitionRow>
              <DefinitionRow term="Created">{formatDateTime(workspace.created_at)}</DefinitionRow>
            </dl>
          ) : (
            <EmptyState title="Unavailable" description="The workspace could not be read." />
          )}
        </Panel>

        <Panel title="Members">
          {!members || members.length === 0 ? (
            <EmptyState title="No members" description="Invite colleagues to this workspace." />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Member</th>
                  <th>Role</th>
                  <th>Joined</th>
                </tr>
              </thead>
              <tbody>
                {members.map((member) => (
                  <tr key={member.id}>
                    <td>
                      <div className="text-ink-100">{member.full_name ?? member.email}</div>
                      <div className="text-2xs text-ink-500">{member.email}</div>
                    </td>
                    <td>
                      <Badge>{member.role}</Badge>
                    </td>
                    <td className="text-2xs text-ink-400">{formatDateTime(member.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel
          title="API keys"
          description="For automation. A key can never administer the workspace or mint another key."
        >
          {!keys || keys.length === 0 ? (
            <EmptyState
              title="No API keys"
              description="Keys are created by an administrator and the plaintext is shown exactly once; only a hash is stored."
            />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Prefix</th>
                  <th>Role</th>
                  <th>Last used</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
                {keys.map((key) => (
                  <tr key={key.id}>
                    <td className="text-ink-100">{key.name}</td>
                    <td className="font-mono text-2xs">{key.key_prefix}••••••••</td>
                    <td>
                      <Badge>{key.role}</Badge>
                    </td>
                    <td className="text-2xs text-ink-400">
                      {key.last_used_at ? formatDateTime(key.last_used_at) : "never"}
                    </td>
                    <td>
                      {key.revoked_at ? (
                        <Badge tone="negative">Revoked</Badge>
                      ) : (
                        <Badge tone="positive">Active</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="Usage (30 days)">
          {usage?.totals ? (
            <>
              <dl>
                {Object.entries(usage.totals).map(([key, value]) => (
                  <DefinitionRow key={key} term={titleCase(key)}>
                    {key.includes("cost") ? formatUsd(value) : value.toLocaleString("en-US")}
                  </DefinitionRow>
                ))}
              </dl>
              {usage.plan ? (
                <div className="border-t border-ink-800 px-4 py-3 text-2xs text-ink-400">
                  Plan: {String(usage.plan.plan ?? "—")} · run limit{" "}
                  {String(usage.plan.research_run_limit ?? "unlimited")}
                </div>
              ) : null}
              <div className="px-4 pb-4 pt-3">
                <Notice tone="caution">
                  Costs are estimates from the configured rate card, not a billing statement.
                </Notice>
              </div>
            </>
          ) : (
            <EmptyState title="No usage recorded" description="Usage appears once agents run." />
          )}
        </Panel>

        <Panel
          title="Provider credentials"
          description="Whether a key is present. The value is never returned to any client."
        >
          {providers ? (
            <dl>
              {Object.entries(providers.credentials_configured).map(([provider, configured]) => (
                <DefinitionRow key={provider} term={titleCase(provider)}>
                  {configured ? (
                    <Badge tone="positive">Configured</Badge>
                  ) : (
                    <Badge tone="neutral">Not configured</Badge>
                  )}
                </DefinitionRow>
              ))}
            </dl>
          ) : (
            <EmptyState title="Unavailable" description="Provider status could not be read." />
          )}
        </Panel>

        <Panel title="Audit trail">
          {!audit || audit.length === 0 ? (
            <EmptyState
              title="No audit entries"
              description="Security-relevant actions are recorded here."
            />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>Outcome</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((entry) => (
                  <tr key={entry.id}>
                    <td className="font-mono text-2xs">{entry.action}</td>
                    <td className="text-2xs text-ink-400">{entry.resource_type ?? "—"}</td>
                    <td>
                      <Badge tone={entry.outcome === "SUCCESS" ? "positive" : "negative"}>
                        {entry.outcome}
                      </Badge>
                    </td>
                    <td className="text-2xs text-ink-400">{formatDateTime(entry.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>

      <div className="mt-4">
        <Notice tone="info">
          Customer data is isolated and is not used for model training unless explicitly
          authorized by an organization owner.
        </Notice>
      </div>
    </>
  );
}
