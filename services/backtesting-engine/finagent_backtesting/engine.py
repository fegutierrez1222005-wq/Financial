"""Portfolio simulator.

Deliberately simple and auditable: daily bars, long-only, close-price execution with
explicit commission and slippage, and a hard rule that signals may only use strictly
earlier bars. An unexplainable backtest is worthless to an institution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from finagent_backtesting.dataset import PriceDataset
from finagent_backtesting.metrics import (
    BacktestMetrics,
    compute_metrics,
    drawdown_series,
    summarise_round_trips,
)
from finagent_backtesting.spec import BacktestSpec
from finagent_backtesting.strategies import generate_signal
from finagent_backtesting.validation import (
    ValidationReport,
    merge_reports,
    validate_execution,
    validate_factor_lag,
    validate_pre_run,
)
from finagent_core.errors import BacktestInvalidError
from finagent_core.logging import get_logger
from finagent_core.schemas.enums import BacktestSplit, RebalanceFrequency

logger = get_logger(__name__)


@dataclass
class Trade:
    trade_date: date
    symbol: str
    side: str  # BUY | SELL
    quantity: float
    price: float
    notional: float
    commission: float
    slippage_cost: float
    realised_pnl: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "date": self.trade_date.isoformat(),
            "symbol": self.symbol,
            "side": self.side,
            "quantity": round(self.quantity, 6),
            "price": round(self.price, 6),
            "notional": round(self.notional, 2),
            "commission": round(self.commission, 2),
            "slippage_cost": round(self.slippage_cost, 2),
            "realised_pnl": round(self.realised_pnl, 2),
        }


@dataclass
class EquityPoint:
    point_date: date
    equity: float
    drawdown_pct: float
    exposure_pct: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "date": self.point_date.isoformat(),
            "equity": round(self.equity, 2),
            "drawdown_pct": round(self.drawdown_pct, 4),
            "exposure_pct": round(self.exposure_pct, 4),
        }


@dataclass
class BacktestResult:
    spec: BacktestSpec
    split: BacktestSplit
    metrics: BacktestMetrics
    equity_curve: list[EquityPoint]
    trades: list[Trade]
    validation: ValidationReport
    rebalance_count: int
    spec_fingerprint: str
    data_fingerprint: str
    is_demo_data: bool
    start_date: date | None = None
    end_date: date | None = None
    final_positions: dict[str, float] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return self.validation.is_valid

    def summary(self) -> dict[str, Any]:
        return {
            "split": self.split.value,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_valid": self.is_valid,
            "is_demo_data": self.is_demo_data,
            "metrics": self.metrics.as_dict(),
            "findings": self.validation.as_list(),
            "rebalance_count": self.rebalance_count,
            "trade_count": len(self.trades),
            "spec_fingerprint": self.spec_fingerprint,
            "data_fingerprint": self.data_fingerprint,
        }


def _rebalance_dates(index: pd.DatetimeIndex, frequency: RebalanceFrequency) -> list[pd.Timestamp]:
    if len(index) == 0:
        return []
    if frequency is RebalanceFrequency.DAILY:
        return list(index)
    alias = {
        RebalanceFrequency.WEEKLY: "W",
        RebalanceFrequency.MONTHLY: "M",
        RebalanceFrequency.QUARTERLY: "Q",
    }[frequency]
    frame = pd.DataFrame(index=index)
    return [group.index[0] for _, group in frame.groupby(index.to_period(alias))]


def run_backtest(
    spec: BacktestSpec,
    dataset: PriceDataset,
    *,
    split: BacktestSplit = BacktestSplit.FULL,
    test_split_use_count: int = 0,
    raise_on_invalid: bool = False,
) -> BacktestResult:
    """Simulate ``spec`` over ``dataset``.

    Validation runs first. When it produces an ``ERROR`` finding the simulation is skipped
    and an invalid result is returned (or :class:`BacktestInvalidError` raised) — the engine
    never emits metrics for a configuration it knows to be untrustworthy.
    """
    window_start, window_end = spec.window_for(split)
    windowed = dataset.window(window_start, window_end)

    pre_report = merge_reports(
        validate_pre_run(spec, windowed, split=split, test_split_use_count=test_split_use_count),
        validate_factor_lag(windowed) if windowed.factors is not None else ValidationReport(),
    )

    if not pre_report.is_valid:
        logger.warning(
            "backtest_invalid",
            extra={"split": split.value, "errors": [item.code.value for item in pre_report.errors]},
        )
        result = BacktestResult(
            spec=spec,
            split=split,
            metrics=BacktestMetrics(),
            equity_curve=[],
            trades=[],
            validation=pre_report,
            rebalance_count=0,
            spec_fingerprint=spec.fingerprint(),
            data_fingerprint=windowed.fingerprint() if not windowed.prices.empty else "",
            is_demo_data=windowed.is_demo,
            start_date=window_start,
            end_date=window_end,
            detail={"skipped": "validation produced blocking errors"},
        )
        if raise_on_invalid:
            raise BacktestInvalidError(
                "backtest configuration failed validation", details={"findings": pre_report.as_list()}
            )
        return result

    prices = windowed.prices
    tradable_mask = prices.notna()
    valuation_prices = prices.ffill()
    index: pd.DatetimeIndex = prices.index
    rebalances = set(_rebalance_dates(index, RebalanceFrequency(spec.rebalance_frequency)))

    cash = spec.initial_capital
    positions: dict[str, float] = {}
    cost_basis: dict[str, float] = {}
    trades: list[Trade] = []
    realised: list[float] = []
    equity_values: list[float] = []
    exposures: list[float] = []
    signal_dates: list[pd.Timestamp] = []
    trade_dates: list[pd.Timestamp] = []
    traded_notional = 0.0
    total_costs = 0.0
    rebalance_count = 0

    slippage_rate = spec.slippage_bps / 10_000.0
    commission_rate = spec.transaction_cost_bps / 10_000.0

    for position, timestamp in enumerate(index):
        row_prices = valuation_prices.loc[timestamp]
        market_value = sum(
            quantity * float(row_prices.get(symbol, np.nan))
            for symbol, quantity in positions.items()
            if not np.isnan(row_prices.get(symbol, np.nan))
        )
        equity = cash + market_value

        if timestamp in rebalances and position >= max(spec.signal_lag_days - 1, 0):
            reference = (
                index[position - (spec.signal_lag_days - 1)] if spec.signal_lag_days >= 1 else timestamp
            )
            signal = generate_signal(windowed, spec, reference)
            if signal.weights:
                rebalance_count += 1
                if signal.signal_date is not None:
                    signal_dates.append(signal.signal_date)
                    trade_dates.append(timestamp)

                targets = {
                    symbol: weight
                    for symbol, weight in signal.weights.items()
                    if symbol in prices.columns and bool(tradable_mask.loc[timestamp, symbol])
                }

                planned: list[tuple[str, float, float]] = []
                for symbol in set(list(positions) + list(targets)):
                    price = float(row_prices.get(symbol, np.nan))
                    if np.isnan(price) or price <= 0:
                        continue
                    if symbol in positions and not bool(tradable_mask.loc[timestamp, symbol]):
                        continue
                    delta = targets.get(symbol, 0.0) * equity / price - positions.get(symbol, 0.0)
                    if abs(delta * price) < max(1.0, equity * 1e-5):
                        continue
                    planned.append((symbol, delta, price))
                planned.sort(key=lambda item: item[1])  # sells (negative) first fund the buys

                for symbol, delta, price in planned:
                    if delta > 0:
                        fill_price = price * (1.0 + slippage_rate)
                        notional = delta * fill_price
                        commission = notional * commission_rate
                        if notional + commission > cash:
                            affordable = max(0.0, (cash - commission) / fill_price)
                            if affordable * fill_price < max(1.0, equity * 1e-5):
                                continue
                            delta = affordable
                            notional = delta * fill_price
                            commission = notional * commission_rate
                        cash -= notional + commission
                        previous_quantity = positions.get(symbol, 0.0)
                        previous_basis = cost_basis.get(symbol, 0.0)
                        new_quantity = previous_quantity + delta
                        cost_basis[symbol] = (
                            (previous_basis * previous_quantity + fill_price * delta) / new_quantity
                            if new_quantity
                            else 0.0
                        )
                        positions[symbol] = new_quantity
                        trades.append(
                            Trade(
                                trade_date=timestamp.date(),
                                symbol=symbol,
                                side="BUY",
                                quantity=delta,
                                price=fill_price,
                                notional=notional,
                                commission=commission,
                                slippage_cost=delta * price * slippage_rate,
                            )
                        )
                    else:
                        quantity = min(-delta, positions.get(symbol, 0.0))
                        if quantity <= 0:
                            continue
                        fill_price = price * (1.0 - slippage_rate)
                        notional = quantity * fill_price
                        commission = notional * commission_rate
                        cash += notional - commission
                        basis = cost_basis.get(symbol, fill_price)
                        pnl = (fill_price - basis) * quantity - commission
                        realised.append(pnl)
                        positions[symbol] = positions.get(symbol, 0.0) - quantity
                        if positions[symbol] <= 1e-9:
                            positions.pop(symbol, None)
                            cost_basis.pop(symbol, None)
                        trades.append(
                            Trade(
                                trade_date=timestamp.date(),
                                symbol=symbol,
                                side="SELL",
                                quantity=quantity,
                                price=fill_price,
                                notional=notional,
                                commission=commission,
                                slippage_cost=quantity * price * slippage_rate,
                                realised_pnl=pnl,
                            )
                        )
                    traded_notional += abs(notional)
                    total_costs += commission + abs(delta) * price * slippage_rate

                market_value = sum(
                    quantity * float(row_prices.get(symbol, 0.0))
                    for symbol, quantity in positions.items()
                )
                equity = cash + market_value

        equity_values.append(equity)
        exposures.append(market_value / equity if equity > 0 else 0.0)

    equity_series = pd.Series(equity_values, index=index, dtype=float)
    exposure_series = pd.Series(exposures, index=index, dtype=float)
    drawdowns = drawdown_series(equity_series)
    equity_points = [
        EquityPoint(
            point_date=timestamp.date(),
            equity=float(equity_series.loc[timestamp]),
            drawdown_pct=float(drawdowns.loc[timestamp]),
            exposure_pct=float(exposure_series.loc[timestamp] * 100.0),
        )
        for timestamp in index
    ]

    trade_stats = summarise_round_trips(realised, total_costs=total_costs, trade_count=len(trades))
    metrics = compute_metrics(
        equity_series,
        exposure=exposure_series,
        trade_stats=trade_stats,
        traded_notional=traded_notional,
        risk_free_rate=spec.risk_free_rate,
    )

    report = merge_reports(
        pre_report,
        validate_execution(
            spec, signal_dates=signal_dates, trade_dates=trade_dates, rebalance_count=rebalance_count
        ),
    )

    logger.info(
        "backtest_completed",
        extra={
            "split": split.value,
            "trades": len(trades),
            "rebalances": rebalance_count,
            "sharpe": round(metrics.sharpe_ratio, 3),
            "is_valid": report.is_valid,
        },
    )

    return BacktestResult(
        spec=spec,
        split=split,
        metrics=metrics,
        equity_curve=equity_points,
        trades=trades,
        validation=report,
        rebalance_count=rebalance_count,
        spec_fingerprint=spec.fingerprint(),
        data_fingerprint=windowed.fingerprint(),
        is_demo_data=windowed.is_demo,
        start_date=index[0].date() if len(index) else window_start,
        end_date=index[-1].date() if len(index) else window_end,
        final_positions={symbol: round(quantity, 6) for symbol, quantity in positions.items()},
        detail={
            "traded_notional": round(traded_notional, 2),
            "ending_cash": round(cash, 2),
            "symbols_simulated": list(prices.columns),
        },
    )
