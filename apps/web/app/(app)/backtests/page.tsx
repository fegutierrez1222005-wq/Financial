import Link from "next/link";
import type { Metadata } from "next";

import { ActionForm } from "@/components/action-form";
import { EmptyState, Notice, PageHeader, Panel } from "@/components/primitives";
import { createBacktest } from "@/app/(app)/actions";
import { apiFetchOrNull } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Backtest } from "@/lib/types";

export const metadata: Metadata = { title: "Backtests" };

export default async function BacktestsPage() {
  const backtests = await apiFetchOrNull<Backtest[]>("/backtests");

  return (
    <>
      <PageHeader
        title="Backtests"
        subtitle="Historical simulation with the assumptions stated on the result. Train, validation and out-of-sample windows are reported separately and never averaged."
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_1.3fr]">
        <Panel title="New backtest">
          <div className="p-4">
            <ActionForm
              action={createBacktest}
              submitLabel="Create backtest"
              pendingLabel="Creating…"
            >
              <div className="space-y-4">
                <div>
                  <label className="field-label" htmlFor="name">
                    Name
                  </label>
                  <input id="name" name="name" required className="field-input" />
                </div>
                <div>
                  <label className="field-label" htmlFor="universe">
                    Universe
                  </label>
                  <input
                    id="universe"
                    name="universe"
                    required
                    className="field-input font-mono text-2xs"
                    defaultValue="ACME, BLTA, CRUX, DELP, EVRG"
                  />
                  <p className="field-hint">
                    Comma-separated symbols. The seeded demo symbols are fictional issuers with
                    synthetic price series.
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="field-label" htmlFor="start_date">
                      Start
                    </label>
                    <input
                      id="start_date"
                      name="start_date"
                      type="date"
                      required
                      defaultValue="2021-01-04"
                      className="field-input numeric"
                    />
                  </div>
                  <div>
                    <label className="field-label" htmlFor="end_date">
                      End
                    </label>
                    <input
                      id="end_date"
                      name="end_date"
                      type="date"
                      required
                      defaultValue="2023-12-29"
                      className="field-input numeric"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="field-label" htmlFor="lookback_days">
                      Lookback (days)
                    </label>
                    <input
                      id="lookback_days"
                      name="lookback_days"
                      type="number"
                      min="5"
                      defaultValue="126"
                      className="field-input numeric"
                    />
                  </div>
                  <div>
                    <label className="field-label" htmlFor="top_n">
                      Positions
                    </label>
                    <input
                      id="top_n"
                      name="top_n"
                      type="number"
                      min="1"
                      defaultValue="3"
                      className="field-input numeric"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="field-label" htmlFor="transaction_cost_bps">
                      Commission (bps)
                    </label>
                    <input
                      id="transaction_cost_bps"
                      name="transaction_cost_bps"
                      type="number"
                      step="0.5"
                      min="0"
                      defaultValue="10"
                      className="field-input numeric"
                    />
                  </div>
                  <div>
                    <label className="field-label" htmlFor="slippage_bps">
                      Slippage (bps)
                    </label>
                    <input
                      id="slippage_bps"
                      name="slippage_bps"
                      type="number"
                      step="0.5"
                      min="0"
                      defaultValue="5"
                      className="field-input numeric"
                    />
                  </div>
                </div>
                <div>
                  <label className="field-label" htmlFor="signal_lag_days">
                    Execution lag (bars)
                  </label>
                  <input
                    id="signal_lag_days"
                    name="signal_lag_days"
                    type="number"
                    min="0"
                    max="10"
                    defaultValue="1"
                    className="field-input numeric"
                  />
                  <p className="field-hint">
                    Bars between observing the signal and trading on it. Zero means trading on the
                    bar that produced the signal — a look-ahead error. The run is still executed so
                    you can see the effect, but it is marked invalid.
                  </p>
                </div>
                <div>
                  <label className="field-label" htmlFor="rebalance_frequency">
                    Rebalance
                  </label>
                  <select
                    id="rebalance_frequency"
                    name="rebalance_frequency"
                    className="field-input"
                    defaultValue="monthly"
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                    <option value="quarterly">Quarterly</option>
                  </select>
                </div>
                <Notice tone="caution">
                  A backtest is a simulation under the assumptions above. It is not a prediction
                  and not investment advice.
                </Notice>
              </div>
            </ActionForm>
          </div>
        </Panel>

        <Panel title="Backtests">
          {!backtests || backtests.length === 0 ? (
            <EmptyState
              title="No backtests yet"
              description="Define one on the left, then run it to see the train, validation and out-of-sample results side by side."
            />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Universe</th>
                  <th>Window</th>
                  <th>Lag</th>
                  <th>Costs</th>
                  <th>OOS uses</th>
                </tr>
              </thead>
              <tbody>
                {backtests.map((backtest) => (
                  <tr key={backtest.id}>
                    <td>
                      <Link href={`/backtests/${backtest.id}`} className="text-ink-100">
                        {backtest.name}
                      </Link>
                    </td>
                    <td className="font-mono text-2xs text-ink-400">
                      {backtest.universe.join(" ")}
                    </td>
                    <td className="text-2xs text-ink-400">
                      {formatDate(backtest.start_date)} → {formatDate(backtest.end_date)}
                    </td>
                    <td className="numeric">
                      {backtest.signal_lag_days === 0 ? (
                        <span className="text-signal-negative">0</span>
                      ) : (
                        backtest.signal_lag_days
                      )}
                    </td>
                    <td className="numeric text-2xs">
                      {backtest.transaction_cost_bps}+{backtest.slippage_bps} bps
                    </td>
                    <td className="numeric">{backtest.test_split_use_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </>
  );
}
