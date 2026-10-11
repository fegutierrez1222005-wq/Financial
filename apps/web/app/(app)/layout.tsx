import Link from "next/link";

import { logout, switchWorkspace } from "@/app/(auth)/actions";
import { Badge } from "@/components/primitives";
import { NavLink } from "@/components/nav-link";
import { apiFetchOrNull, currentWorkspaceId } from "@/lib/api";
import type { Workspace } from "@/lib/types";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/agents", label: "Agents" },
  { href: "/research", label: "Research" },
  { href: "/evaluations", label: "Evaluations" },
  { href: "/leaderboard", label: "Leaderboard" },
  { href: "/experiments", label: "Experiments" },
  { href: "/backtests", label: "Backtests" },
  { href: "/data", label: "Data" },
  { href: "/settings", label: "Settings" },
];

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const workspaces = (await apiFetchOrNull<Workspace[]>("/workspaces")) ?? [];
  const activeId = await currentWorkspaceId();
  const active = workspaces.find((workspace) => workspace.id === activeId) ?? workspaces[0];

  return (
    <div className="flex min-h-screen flex-col bg-ink-950">
      <header className="sticky top-0 z-20 border-b border-ink-800 bg-ink-950/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-6 gap-y-3 px-6 py-3">
          <Link
            href="/dashboard"
            className="font-mono text-sm font-semibold tracking-[0.2em] text-ink-100 no-underline"
          >
            FINAGENT&nbsp;LAB
          </Link>

          <form action={switchWorkspace} className="flex items-center gap-2">
            <label className="sr-only" htmlFor="workspace_id">
              Active workspace
            </label>
            <select
              id="workspace_id"
              name="workspace_id"
              defaultValue={active?.id}
              className="rounded border border-ink-600 bg-ink-850 px-2.5 py-1.5 text-sm text-ink-200"
            >
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                  {workspace.is_demo ? " (demo)" : ""}
                </option>
              ))}
            </select>
            <button type="submit" className="button-secondary px-2.5 py-1.5 text-2xs">
              Switch
            </button>
          </form>

          {active?.is_demo ? <Badge tone="mock">Demo workspace</Badge> : null}
          {active?.role ? <Badge>{active.role}</Badge> : null}

          <form action={logout} className="ml-auto">
            <button type="submit" className="button-secondary px-2.5 py-1.5 text-2xs">
              Sign out
            </button>
          </form>
        </div>

        <nav className="border-t border-ink-800">
          <ul className="mx-auto flex max-w-[1400px] gap-1 overflow-x-auto px-4">
            {NAV.map((item) => (
              <li key={item.href}>
                <NavLink href={item.href}>{item.label}</NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-8">{children}</main>

      <footer className="border-t border-ink-800 px-6 py-5">
        <p className="mx-auto max-w-[1400px] text-2xs leading-relaxed text-ink-500">
          Scores measure research process quality and do not predict investment returns. Backtests
          are historical simulations under stated assumptions and are not investment advice.
        </p>
      </footer>
    </div>
  );
}
