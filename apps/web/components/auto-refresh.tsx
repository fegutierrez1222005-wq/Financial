"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

/** Statuses that will not change on their own. */
const TERMINAL = new Set(["SUCCEEDED", "FAILED", "CANCELLED"]);

export function isTerminal(status: string | null | undefined): boolean {
  return status === null || status === undefined || TERMINAL.has(status);
}

/**
 * Re-fetch the current route while the work it shows is still running.
 *
 * With the inline job backend a run has already finished by the time the page renders.
 * With a Celery worker it has not, so without this the user is left looking at a page
 * that says QUEUED and never changes — the product would appear broken in exactly the
 * configuration it is meant to be deployed in.
 *
 * Polling backs off and then stops rather than hammering the API forever: a job still
 * queued after several minutes needs the maintenance sweep, not another request.
 */
export function AutoRefresh({
  status,
  label = "work",
  initialIntervalMs = 2_000,
  maxIntervalMs = 15_000,
  giveUpAfterMs = 10 * 60_000,
}: {
  status: string | null | undefined;
  label?: string;
  initialIntervalMs?: number;
  maxIntervalMs?: number;
  giveUpAfterMs?: number;
}) {
  const router = useRouter();
  const [intervalMs, setIntervalMs] = useState(initialIntervalMs);
  const [elapsedMs, setElapsedMs] = useState(0);
  const settled = isTerminal(status);
  const gaveUp = elapsedMs >= giveUpAfterMs;

  useEffect(() => {
    if (settled || gaveUp) return;
    const timer = setTimeout(() => {
      setElapsedMs((previous) => previous + intervalMs);
      setIntervalMs((previous) => Math.min(previous * 1.5, maxIntervalMs));
      router.refresh();
    }, intervalMs);
    return () => clearTimeout(timer);
  }, [router, intervalMs, elapsedMs, settled, gaveUp, maxIntervalMs, giveUpAfterMs]);

  if (settled) return null;

  return (
    <p
      role="status"
      aria-live="polite"
      className="rounded border border-signal-info/40 bg-signal-info/5 px-3.5 py-2.5 text-2xs text-ink-200"
    >
      {gaveUp ? (
        <>
          This {label} has not reported a result for several minutes and the page has
          stopped refreshing. Reload to check again — a worker that died mid-job is marked
          failed by the maintenance sweep.
        </>
      ) : (
        <>
          <span className="mr-2 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-signal-info align-middle" />
          Running on a worker. This page refreshes itself until the {label} reports a
          result.
        </>
      )}
    </p>
  );
}
