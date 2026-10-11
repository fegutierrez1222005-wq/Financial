import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { SubmitButton } from "@/components/action-form";
import {
  Badge,
  DefinitionRow,
  EmptyState,
  EquityCurve,
  Notice,
  PageHeader,
  Panel,
} from "@/components/primitives";
import { AutoRefresh } from "@/components/auto-refresh";
import { runBacktest } from "@/app/(app)/actions";
import { apiFetchOrNull } from "@/lib/api";
import { EMPTY, formatDate, formatNumber, formatPercent, formatUsd } from "@/lib/format";
import type { BacktestDetail, BacktestSplit } from "@/lib/types";

export const metadata: Metadata = { title: "Backtest" };

const SPLIT_LABEL: Record<string, string> = {
  full: "Full period",
  train: "Train (in-sample)",
  validation: "Validation",
  test: "Test (out-of-sample)",
};

const HEADLINE_METRICS = [
  { key: "total_return_pct", label: "Total return", kind: "percent" },
  { key: "cagr_pct", label: "CAGR", kind: "percent" },
  { key: "sharpe_ratio", label: "Sharpe", kind: "number" },
  { key: "sortino_ratio", label: "Sortino", kind: "number" },
  { key: "max_drawdown_pct", label: "Max drawdown", kind: "percent" },
  { key: "annualised_volatility_pct", label: "Volatility", kind: "percent" },
  { key: "win_rate", label: "Win rate", kind: "percent" },
  { key: "total_costs", label: "Costs paid", kind: "usd" },
  { key: "calmar_ratio", label: "Calmar", kind: "number" },
  { key: "profit_factor", label: "Profit factor", kind: "number" },
  { key: "annual_turnover_pct", label: "Turnover", kind: "percent" },
  { key: "average_exposure_pct", label: "Avg exposure", kind: "percent" },
] as const;

function MetricValue({ kind, value }: { kind: string; value: number | undefined }) {
  if (value === undefined) return <span className="text-ink-500">{EMPTY}</span>;
  if (kind === "percent") return <>{formatPercent(value)}</>;
  if (kind === "usd") return <>{formatUsd(value)}</>;
  return <>{formatNumber(value)}</>;
}

function SplitPanel({ split }: { split: BacktestSplit }) {
  return (
    <Panel
      title={SPLIT_LABEL[split.split] ?? split.split}
      description={
        split.start_date && split.end_date
          ? `${formatDate(split.start_date)} → ${formatDate(split.end_date)}`
          : undefined
      }
      action={
        <span className="flex gap-1.5">
          {split.is_valid ? (
            <Badge tone="positive">Valid</Badge>
          ) : (
            <Badge tone="negative">Invalid</Badge>
          )}
          {split.is_demo_data ? <Badge tone="mock">Demo prices</Badge> : null}
        </span>
      }
    >
      {!split.is_valid ? (
        <div className="px-4 pt-4">
          <Notice tone="negative">
            This result is not usable. The findings below explain why; it is shown so the cause is
            visible, not so it can be interpreted.
          </Notice>
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-x-6 gap-y-3 px-4 py-4 sm:grid-cols-4">
        {HEADLINE_METRICS.map((metric) => (
          <div key={metric.key}>
            <div className="text-2xs uppercase tracking-[0.1em] text-ink-400">{metric.label}</div>
            <div className="numeric mt-1 text-sm text-ink-100">
              <MetricValue kind={metric.kind} value={split.metrics[metric.key]} />
            </div>
          </div>
        ))}
      </div>

      {split.equity_curve.length > 1 ? (
        <div className="border-t border-ink-800 px-4 py-4">
          <EquityCurve points={split.equity_curve} />
        </div>
      ) : null}

      <div className="border-t border-ink-800 px-4 py-3 text-2xs text-ink-400">
        {split.rebalance_count} rebalances · {split.trade_count} trades
      </div>

      {split.findings.length > 0 ? (
        <ul className="divide-y divide-ink-800 border-t border-ink-800">
          {split.findings.map((finding, index) => (
            <li key={index} className="px-4 py-2.5">
              <div className="flex items-center gap-2">
                <Badge
                  tone={
                    finding.severity === "ERROR" || finding.severity === "BLOCKING"
                      ? "negative"
                      : finding.severity === "WARNING"
                        ? "caution"
                        : "neutral"
                  }
                >
                  {finding.severity ?? "INFO"}
                </Badge>
                <span className="text-sm text-ink-200">{finding.title ?? finding.code}</span>
              </div>
              <p className="mt-1 text-2xs leading-relaxed text-ink-400">{finding.message}</p>
            </li>
          ))}
        </ul>
      ) : null}
    </Panel>
  );
}

/**
 * How much the strategy decayed from the training window to the out-of-sample one.
 * Shown as a stated verdict rather than a number the reader has to interpret.
 */
function OverfittingPanel({ report }: { report: Record<string, unknown> }) {
  const severity = String(report.severity ?? "INFO");
  const sharpes = [
    { label: "Train", value: report.train_sharpe },
    { label: "Validation", value: report.validation_sharpe },
    { label: "Test", value: report.test_sharpe },
  ].filter((entry) => typeof entry.value === "number");

  return (
    <Panel
      title="Overfitting check"
      action={
        <Badge
          tone={severity === "ERROR" ? "negative" : severity === "WARNING" ? "caution" : "neutral"}
        >
          {severity}
        </Badge>
      }
    >
      <p className="px-4 py-3 text-2xs leading-relaxed text-ink-300">
        {String(report.verdict ?? "No verdict was recorded.")}
      </p>
      {sharpes.length > 0 ? (
        <div className="grid grid-cols-3 divide-x divide-ink-800 border-t border-ink-800">
          {sharpes.map((entry) => (
            <div key={entry.label} className="px-4 py-3">
              <div className="text-2xs uppercase tracking-[0.1em] text-ink-400">
                {entry.label} Sharpe
              </div>
              <div className="numeric mt-1 text-sm text-ink-100">
                {formatNumber(entry.value as number)}
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {typeof report.degradation_pct === "number" ? (
        <div className="border-t border-ink-800 px-4 py-2.5 text-2xs text-ink-400">
          Degradation from train to test: {formatPercent(report.degradation_pct)}
        </div>
      ) : null}
    </Panel>
  );
}

export default async function BacktestPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ awaiting?: string }>;
}) {
  const { id } = await params;
  const { awaiting } = await searchParams;
  const detail = await apiFetchOrNull<BacktestDetail>(`/backtests/${id}?include_trades=true`);
  if (!detail) notFound();

  const { backtest } = detail;
  const order = ["full", "train", "validation", "test"];
  const splits = [...detail.runs].sort(
    (a, b) => order.indexOf(a.split) - order.indexOf(b.split),
  );
  const awaitingResult =
    awaiting === "1" &&
    (splits.length === 0 || splits.some((split) => !["SUCCEEDED", "FAILED"].includes(split.status)));

  return (
    <>
      <PageHeader
        title={backtest.name}
        subtitle={backtest.description ?? undefined}
        action={
          <form action={runBacktest}>
            <input type="hidden" name="backtest_id" value={backtest.id} />
            <SubmitButton
              label={splits.length ? "Run again" : "Run backtest"}
              pendingLabel="Simulating…"
            />
          </form>
        }
      />

      <div className="mb-4 space-y-3">
        <AutoRefresh
          status={awaitingResult ? "RUNNING" : "SUCCEEDED"}
          label="backtest"
          giveUpAfterMs={5 * 60_000}
        />
        <Notice tone="caution">{detail.disclaimer}</Notice>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_2fr]">
        <div className="space-y-4">
          <Panel title="Assumptions">
            <dl>
              <DefinitionRow term="Universe">{backtest.universe.join(", ")}</DefinitionRow>
              <DefinitionRow term="Period">
                {formatDate(backtest.start_date)} → {formatDate(backtest.end_date)}
              </DefinitionRow>
              <DefinitionRow term="Rebalance">{backtest.rebalance_frequency}</DefinitionRow>
              <DefinitionRow term="Commission">{backtest.transaction_cost_bps} bps</DefinitionRow>
              <DefinitionRow term="Slippage">{backtest.slippage_bps} bps</DefinitionRow>
              <DefinitionRow term="Execution lag">
                {backtest.signal_lag_days === 0 ? (
                  <span className="text-signal-negative">0 bars (look-ahead)</span>
                ) : (
                  `${backtest.signal_lag_days} bar(s)`
                )}
              </DefinitionRow>
              <DefinitionRow term="Initial capital">
                {formatUsd(backtest.initial_capital)}
              </DefinitionRow>
              <DefinitionRow term="Out-of-sample uses">
                {detail.test_split_use_count}
              </DefinitionRow>
            </dl>
            <div className="border-t border-ink-800 px-4 py-3">
              <Notice tone="info">{detail.reporting_note}</Notice>
            </div>
          </Panel>

          {detail.overfitting ? <OverfittingPanel report={detail.overfitting} /> : null}
        </div>

        <div className="space-y-4">
          {splits.length === 0 ? (
            <Panel>
              <EmptyState
                title="Not run yet"
                description="Run the backtest to produce in-sample, validation and out-of-sample results."
              />
            </Panel>
          ) : (
            splits.map((split) => <SplitPanel key={split.id} split={split} />)
          )}
        </div>
      </div>
    </>
  );
}
