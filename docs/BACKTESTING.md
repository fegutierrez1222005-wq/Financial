# Backtesting

A backtest is a historical simulation under stated assumptions. It is not a prediction, it
is not advice, and the platform will not let it pretend to be either.

---

## 1. The one rule that matters

**A signal may never be computed from the bar it trades on.**

```python
def history_for(self, as_of, lookback):
    """Price history strictly *before* ``as_of`` — the look-ahead firewall."""
    return self.prices.loc[self.prices.index < pd.Timestamp(as_of)].tail(lookback)
```

Every strategy signal derives from this method. Because it excludes `as_of` itself, the
firewall holds structurally rather than by convention: there is no path by which a strategy
can observe the bar it is about to trade.

On top of that, `signal_lag_days` defaults to **1**: the signal is observed on day *t* and
executed at day *t+1*'s price. Setting it to **0** means trading on the signal bar, which
is a look-ahead error. The run still executes — so the user can see the inflated numbers
it produces — but it is marked `is_valid = false` and carries a blocking
`LOOK_AHEAD_SIGNAL_LAG` finding, and the UI renders it as invalid rather than as a result.

> Asserted by `test_backtest_with_future_information_is_rejected` and
> `test_backtest_history_excludes_the_traded_bar`.

---

## 2. Costs

Returns reported without costs are fiction. Every fill pays:

| Component | Default | Applied |
| --- | --- | --- |
| Commission | 10 bps | On traded notional, both sides |
| Slippage | 5 bps | On traded notional, against the trade |

Both are configurable per backtest and both are reported on the result, so a reader can see
what was assumed instead of inferring it. `total_costs` is a headline metric.

---

## 3. Splits

The window is divided **sequentially** — never randomly, because shuffling time-series data
leaks the future into the past:

```
|------------ train 50% ------------|--- validation 25% ---|--- test 25% ---|
```

Each split is simulated independently and reported separately. **They are never averaged.**
An average across in-sample and out-of-sample windows is a number with no meaning.

`test_split_use_count` increments every time the out-of-sample window is run. Repeated use
turns out-of-sample into in-sample by degrees; the counter is displayed so the degradation
is visible rather than forgotten.

---

## 4. Overfitting

After a full run the engine compares Sharpe across splits:

- Material decay from train to test raises a `WARNING`.
- A sign flip — profitable in training, loss-making out of sample — raises an `ERROR`.
- If the training window itself was not profitable, the comparison returns early with
  "the training window was not profitable, so the comparison is not meaningful."

That last case matters: a degradation percentage computed from a negative baseline is
arithmetic noise, and reporting it as a finding would be worse than reporting nothing.

---

## 5. Metrics

`total_return_pct`, `cagr_pct`, `annualised_volatility_pct`, `sharpe_ratio`,
`sortino_ratio`, `max_drawdown_pct`, `calmar_ratio`, `daily_hit_rate`, `best_day_pct`,
`worst_day_pct`, `average_exposure_pct`, `annual_turnover_pct`, `trade_count`,
`round_trips`, `win_rate`, `profit_factor`, `total_costs`, `trading_days`.

Sharpe uses the configured risk-free rate and 252 trading days. Drawdown is peak-to-trough
on the equity curve, reported as a positive percentage.

---

## 6. Findings the engine always reports

Every result carries the caveats that apply to it, whether or not anyone asked:

| Code | Severity | Why |
| --- | --- | --- |
| `LOOK_AHEAD_SIGNAL_LAG` | ERROR | `signal_lag_days = 0` |
| `SURVIVORSHIP_STATIC_UNIVERSE` | WARNING | The universe is a fixed symbol list, not point-in-time index membership. Delisted and acquired companies are absent, so results are survivorship-biased. |
| `DEMO_DATA` | WARNING | The run used the synthetic demo price series and says nothing about real markets. |
| `SHORT_HISTORY` | WARNING | Too few bars for the statistics to mean much. |
| `MISSING_PRICES` | WARNING | Gaps in the panel, with the affected symbols named. |
| `UNADJUSTED_PRICES` | WARNING | The provider returned prices not adjusted for splits or dividends. |
| `FEW_REBALANCES` | WARNING | Too few rebalances for the result to be distinguishable from luck. |
| `OVERFITTING_DEGRADATION` | WARNING/ERROR | Out-of-sample performance decayed materially. |

---

## 7. Reproducibility

Each run records a `data_fingerprint` (a content hash of the price panel) and a
`spec_fingerprint` (a hash of the configuration). Two runs with identical fingerprints must
produce identical metrics; different metrics with identical fingerprints is a bug in the
simulator, and the fingerprints are what make that detectable.

---

## 8. Factor data and publication lag

Fundamental factors carry both a `period_end` and a `publication_timestamp`, and
`factors_available_at(as_of)` returns only observations published strictly before `as_of`.
A quarter ending 31 March is not usable on 1 April — the demo dataset applies a 45-day
publication lag, which is roughly when the filing would actually have appeared.

---

## 9. What is deliberately not modelled

Stated plainly, because an unstated simplification is a lie by omission:

- **Market impact.** Slippage is a flat spread cost, not a function of participation rate.
- **Borrow cost and availability.** There is no short side in V1.
- **Point-in-time index membership.** Hence the survivorship warning on every run.
- **Corporate actions beyond price adjustment.** Mergers and spin-offs are not simulated.
- **Intraday execution.** Fills occur at the bar's close.
- **Live trading.** There is no execution path, by design.
