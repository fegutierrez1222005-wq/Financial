import type { ReactNode } from "react";

import { EMPTY } from "@/lib/format";

export function Panel({
  title,
  action,
  children,
  description,
  className = "",
}: {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
  description?: string;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title ? (
        <header className="panel-header">
          <div>
            <h2 className="panel-title">{title}</h2>
            {description ? (
              <p className="mt-1 text-2xs text-ink-400">{description}</p>
            ) : null}
          </div>
          {action}
        </header>
      ) : null}
      {children}
    </section>
  );
}

export function Metric({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "neutral" | "positive" | "negative" | "caution";
}) {
  const toneClass = {
    neutral: "text-ink-100",
    positive: "text-signal-positive",
    negative: "text-signal-negative",
    caution: "text-signal-caution",
  }[tone];

  return (
    <div className="px-4 py-3">
      <div className="text-2xs font-semibold uppercase tracking-[0.12em] text-ink-400">{label}</div>
      <div className={`numeric mt-1.5 text-xl ${toneClass}`}>{value}</div>
      {hint ? <div className="mt-1 text-2xs leading-snug text-ink-500">{hint}</div> : null}
    </div>
  );
}

const BADGE_TONES = {
  neutral: "border-ink-600 bg-ink-800 text-ink-300",
  positive: "border-signal-positive/50 bg-signal-positive/10 text-signal-positive",
  negative: "border-signal-negative/50 bg-signal-negative/10 text-signal-negative",
  caution: "border-signal-caution/50 bg-signal-caution/10 text-signal-caution",
  info: "border-signal-info/50 bg-signal-info/10 text-signal-info",
  mock: "border-signal-mock/50 bg-signal-mock/10 text-signal-mock",
} as const;

export type BadgeTone = keyof typeof BADGE_TONES;

export function Badge({
  children,
  tone = "neutral",
  title,
}: {
  children: ReactNode;
  tone?: BadgeTone;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded-sm border px-1.5 py-0.5 text-2xs font-medium uppercase tracking-[0.08em] ${BADGE_TONES[tone]}`}
    >
      {children}
    </span>
  );
}

const STATUS_TONES: Record<string, BadgeTone> = {
  SUCCEEDED: "positive",
  RUNNING: "info",
  QUEUED: "neutral",
  FAILED: "negative",
  CANCELLED: "caution",
  INDEXED: "positive",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={STATUS_TONES[status] ?? "neutral"}>{status}</Badge>;
}

/**
 * Marks output produced by the deterministic local provider or the demo corpus.
 * Simulated output is never allowed to render as if it were live.
 */
export function ProvenanceBadges({
  usedMockModel,
  usedDemoData,
}: {
  usedMockModel?: boolean;
  usedDemoData?: boolean;
}) {
  if (!usedMockModel && !usedDemoData) return null;
  return (
    <span className="inline-flex gap-1.5">
      {usedMockModel ? (
        <Badge tone="mock" title="Produced by the deterministic local provider, not a language model.">
          Simulated model
        </Badge>
      ) : null}
      {usedDemoData ? (
        <Badge tone="mock" title="Derived from the fictional ACME Technologies demo corpus.">
          Demo data
        </Badge>
      ) : null}
    </span>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <p className="text-sm font-medium text-ink-200">{title}</p>
      <p className="max-w-md text-sm leading-relaxed text-ink-400">{description}</p>
      {action}
    </div>
  );
}

export function Notice({
  tone = "info",
  children,
}: {
  tone?: "info" | "caution" | "negative" | "mock";
  children: ReactNode;
}) {
  const tones = {
    info: "border-signal-info/40 bg-signal-info/5 text-ink-200",
    caution: "border-signal-caution/40 bg-signal-caution/5 text-ink-200",
    negative: "border-signal-negative/40 bg-signal-negative/5 text-ink-200",
    mock: "border-signal-mock/40 bg-signal-mock/5 text-ink-200",
  }[tone];
  return (
    <p className={`rounded border px-3.5 py-2.5 text-2xs leading-relaxed ${tones}`}>{children}</p>
  );
}

export function DefinitionRow({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-6 border-b border-ink-800 px-4 py-2 last:border-b-0">
      <dt className="text-2xs uppercase tracking-[0.1em] text-ink-400">{term}</dt>
      <dd className="numeric text-sm text-ink-200">{children ?? EMPTY}</dd>
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-ink-100">{title}</h1>
        {subtitle ? <p className="mt-1 max-w-3xl text-sm text-ink-400">{subtitle}</p> : null}
      </div>
      {action}
    </div>
  );
}

/**
 * Equity curve rendered as inline SVG from the points the simulator produced.
 * No smoothing and no interpolation: the line is the data.
 */
export function EquityCurve({
  points,
  height = 120,
}: {
  points: Array<{ date: string; equity: number; drawdown_pct: number }>;
  height?: number;
}) {
  if (points.length < 2) return null;

  const width = 640;
  const values = points.map((point) => point.equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;

  const path = points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * width;
      const y = height - ((point.equity - min) / span) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  const start = points[0].equity;
  const end = points[points.length - 1].equity;
  const stroke = end >= start ? "#2f9e6d" : "#d2504b";
  const worst = Math.max(...points.map((point) => point.drawdown_pct));

  return (
    <figure>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="h-28 w-full"
        role="img"
        aria-label={`Equity curve from ${points[0].date} to ${points[points.length - 1].date}`}
      >
        <path d={path} fill="none" stroke={stroke} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
      </svg>
      <figcaption className="mt-2 flex justify-between font-mono text-2xs text-ink-500">
        <span>{points[0].date}</span>
        <span>worst drawdown {worst.toFixed(1)}%</span>
        <span>{points[points.length - 1].date}</span>
      </figcaption>
    </figure>
  );
}

/** A horizontal 0–100 bar. Used for scores only, never for returns. */
export function ScoreBar({ value }: { value: number | null }) {
  if (value === null || value === undefined) {
    return <span className="text-ink-500">{EMPTY}</span>;
  }
  const tone =
    value >= 85 ? "bg-signal-positive" : value >= 65 ? "bg-signal-caution" : "bg-signal-negative";
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 w-24 overflow-hidden rounded-sm bg-ink-700">
        <span
          className={`block h-full ${tone}`}
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </span>
      <span className="numeric text-sm">{value.toFixed(1)}</span>
    </span>
  );
}
