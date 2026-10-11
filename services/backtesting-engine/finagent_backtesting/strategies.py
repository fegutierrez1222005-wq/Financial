"""Strategy signal generation.

Every strategy receives only :meth:`PriceDataset.history_for`, which excludes the bar being
traded. Signals therefore cannot see the present or the future by construction rather than
by convention.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from finagent_backtesting.dataset import PriceDataset
from finagent_backtesting.spec import BacktestSpec, StrategyKind


@dataclass(frozen=True)
class SignalResult:
    """Target weights for a rebalance, plus the last bar the signal observed."""

    weights: dict[str, float]
    signal_date: pd.Timestamp | None
    detail: dict[str, float]


def _normalise_weights(scores: pd.Series, spec: BacktestSpec) -> dict[str, float]:
    selected = scores.dropna().sort_values(ascending=spec.strategy.ascending).head(spec.strategy.top_n)
    if selected.empty:
        return {}
    equal_weight = min(spec.max_position_weight, 1.0 / len(selected))
    investable = 1.0 - spec.min_cash_buffer
    weights = dict.fromkeys(selected.index, equal_weight)
    total = sum(weights.values())
    if total > investable and total > 0:
        scale = investable / total
        weights = {symbol: weight * scale for symbol, weight in weights.items()}
    return weights


def momentum_signal(dataset: PriceDataset, spec: BacktestSpec, as_of: pd.Timestamp) -> SignalResult:
    lookback = spec.strategy.lookback_days + spec.strategy.skip_recent_days + 1
    history = dataset.history_for(as_of, lookback)
    if len(history) < spec.strategy.lookback_days + 1:
        return SignalResult({}, history.index[-1] if len(history) else None, {})
    if spec.strategy.skip_recent_days:
        history = history.iloc[: len(history) - spec.strategy.skip_recent_days]
    if len(history) < 2:
        return SignalResult({}, history.index[-1] if len(history) else None, {})
    returns = (history.iloc[-1] / history.iloc[0] - 1.0) * 100.0
    return SignalResult(
        _normalise_weights(returns, spec),
        history.index[-1],
        {symbol: float(value) for symbol, value in returns.dropna().items()},
    )


def low_volatility_signal(dataset: PriceDataset, spec: BacktestSpec, as_of: pd.Timestamp) -> SignalResult:
    history = dataset.history_for(as_of, spec.strategy.lookback_days + 1)
    if len(history) < 10:
        return SignalResult({}, history.index[-1] if len(history) else None, {})
    volatility = history.pct_change().std(ddof=1) * np.sqrt(252) * 100.0
    selected = volatility.dropna().sort_values(ascending=True).head(spec.strategy.top_n)
    equal_weight = min(spec.max_position_weight, 1.0 / max(len(selected), 1))
    return SignalResult(
        dict.fromkeys(selected.index, equal_weight),
        history.index[-1],
        {symbol: float(value) for symbol, value in volatility.dropna().items()},
    )


def factor_rank_signal(dataset: PriceDataset, spec: BacktestSpec, as_of: pd.Timestamp) -> SignalResult:
    factors = dataset.factors_available_at(as_of)
    history = dataset.history_for(as_of, 2)
    signal_date = history.index[-1] if len(history) else None
    factor_name = spec.strategy.factor or ""
    if factors.empty or factor_name not in factors.columns:
        return SignalResult({}, signal_date, {})
    scores = factors[factor_name].astype(float)
    scores = scores[[symbol for symbol in scores.index if symbol in dataset.prices.columns]]
    return SignalResult(
        _normalise_weights(scores, spec),
        signal_date,
        {symbol: float(value) for symbol, value in scores.dropna().items()},
    )


def equal_weight_signal(dataset: PriceDataset, spec: BacktestSpec, as_of: pd.Timestamp) -> SignalResult:
    history = dataset.history_for(as_of, 2)
    if history.empty:
        return SignalResult({}, None, {})
    tradable = [symbol for symbol in dataset.prices.columns if not np.isnan(history.iloc[-1][symbol])]
    if not tradable:
        return SignalResult({}, history.index[-1], {})
    weight = min(spec.max_position_weight, (1.0 - spec.min_cash_buffer) / len(tradable))
    return SignalResult(dict.fromkeys(tradable, weight), history.index[-1], {})


_STRATEGIES = {
    StrategyKind.CROSS_SECTIONAL_MOMENTUM: momentum_signal,
    StrategyKind.LOW_VOLATILITY: low_volatility_signal,
    StrategyKind.FACTOR_RANK: factor_rank_signal,
    StrategyKind.EQUAL_WEIGHT_BUY_HOLD: equal_weight_signal,
}


def generate_signal(dataset: PriceDataset, spec: BacktestSpec, as_of: pd.Timestamp) -> SignalResult:
    handler = _STRATEGIES.get(StrategyKind(spec.strategy.kind))
    if handler is None:  # pragma: no cover - guarded by spec validation
        raise ValueError(f"unsupported strategy kind: {spec.strategy.kind}")
    return handler(dataset, spec, as_of)
