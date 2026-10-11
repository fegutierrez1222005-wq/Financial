"""Performance and risk metrics.

Returns alone are never reported: risk, drawdown, turnover and trade statistics accompany
them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass
class TradeStats:
    trade_count: int = 0
    round_trips: int = 0
    win_rate: float = 0.0
    #: None when there were no losing trades: the ratio is undefined, not infinite.
    profit_factor: float | None = None
    average_win: float = 0.0
    average_loss: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    total_costs: float = 0.0


@dataclass
class BacktestMetrics:
    total_return_pct: float = 0.0
    cagr_pct: float = 0.0
    annualised_volatility_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    calmar_ratio: float = 0.0
    daily_hit_rate: float = 0.0
    best_day_pct: float = 0.0
    worst_day_pct: float = 0.0
    average_exposure_pct: float = 0.0
    annual_turnover_pct: float = 0.0
    trade_count: int = 0
    round_trips: int = 0
    win_rate: float = 0.0
    #: None when there were no losing trades; see TradeStats.
    profit_factor: float | None = None
    total_costs: float = 0.0
    trading_days: int = 0
    detail: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, float | None]:
        return {
            "total_return_pct": self.total_return_pct,
            "cagr_pct": self.cagr_pct,
            "annualised_volatility_pct": self.annualised_volatility_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown_pct": self.max_drawdown_pct,
            "calmar_ratio": self.calmar_ratio,
            "daily_hit_rate": self.daily_hit_rate,
            "best_day_pct": self.best_day_pct,
            "worst_day_pct": self.worst_day_pct,
            "average_exposure_pct": self.average_exposure_pct,
            "annual_turnover_pct": self.annual_turnover_pct,
            "trade_count": float(self.trade_count),
            "round_trips": float(self.round_trips),
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_costs": self.total_costs,
            "trading_days": float(self.trading_days),
        }


def max_drawdown(equity: pd.Series) -> float:
    """Maximum peak-to-trough decline as a positive percentage."""
    if equity.empty:
        return 0.0
    return float(abs((equity / equity.cummax() - 1.0).min()) * 100.0)


def drawdown_series(equity: pd.Series) -> pd.Series:
    if equity.empty:
        return equity
    return (equity / equity.cummax() - 1.0) * 100.0


def compute_metrics(
    equity: pd.Series,
    *,
    exposure: pd.Series | None = None,
    trade_stats: TradeStats | None = None,
    traded_notional: float = 0.0,
    risk_free_rate: float = 0.02,
) -> BacktestMetrics:
    """Compute the metric set from a daily equity curve."""
    metrics = BacktestMetrics()
    if equity.empty or len(equity) < 2:
        return metrics

    equity = equity.astype(float)
    returns = equity.pct_change().dropna()
    metrics.trading_days = len(equity)
    metrics.total_return_pct = float((equity.iloc[-1] / equity.iloc[0] - 1.0) * 100.0)

    years = max(len(equity) / TRADING_DAYS, 1.0 / TRADING_DAYS)
    if equity.iloc[0] > 0 and equity.iloc[-1] > 0:
        metrics.cagr_pct = float(((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0) * 100.0)

    if not returns.empty:
        daily_std = float(returns.std(ddof=1))
        metrics.annualised_volatility_pct = daily_std * np.sqrt(TRADING_DAYS) * 100.0
        daily_rf = (1.0 + risk_free_rate) ** (1.0 / TRADING_DAYS) - 1.0
        excess = returns - daily_rf
        if daily_std > 0:
            metrics.sharpe_ratio = float(excess.mean() / daily_std * np.sqrt(TRADING_DAYS))
        downside = excess[excess < 0]
        downside_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
        if downside_std > 0:
            metrics.sortino_ratio = float(excess.mean() / downside_std * np.sqrt(TRADING_DAYS))
        metrics.daily_hit_rate = float((returns > 0).mean() * 100.0)
        metrics.best_day_pct = float(returns.max() * 100.0)
        metrics.worst_day_pct = float(returns.min() * 100.0)

    metrics.max_drawdown_pct = max_drawdown(equity)
    if metrics.max_drawdown_pct > 0:
        metrics.calmar_ratio = float(metrics.cagr_pct / metrics.max_drawdown_pct)

    if exposure is not None and not exposure.empty:
        metrics.average_exposure_pct = float(exposure.mean() * 100.0)

    average_equity = float(equity.mean())
    if average_equity > 0 and years > 0:
        # Turnover: one-way traded notional relative to average capital, annualised.
        metrics.annual_turnover_pct = float(traded_notional / average_equity / years * 100.0)

    if trade_stats is not None:
        metrics.trade_count = trade_stats.trade_count
        metrics.round_trips = trade_stats.round_trips
        metrics.win_rate = trade_stats.win_rate
        metrics.profit_factor = trade_stats.profit_factor
        metrics.total_costs = trade_stats.total_costs
        metrics.detail.update(
            {
                "average_win": trade_stats.average_win,
                "average_loss": trade_stats.average_loss,
                "gross_profit": trade_stats.gross_profit,
                "gross_loss": trade_stats.gross_loss,
            }
        )
    return metrics


def summarise_round_trips(realised: list[float], *, total_costs: float, trade_count: int) -> TradeStats:
    """Aggregate realised round-trip P&L into win rate and profit factor."""
    wins = [value for value in realised if value > 0]
    losses = [value for value in realised if value < 0]
    gross_profit = float(sum(wins))
    gross_loss = float(abs(sum(losses)))
    return TradeStats(
        trade_count=trade_count,
        round_trips=len(realised),
        win_rate=float(len(wins) / len(realised) * 100.0) if realised else 0.0,
        # With no losing trade the ratio is undefined, not infinite. Reporting None says
        # "there is nothing to divide by"; reporting inf would read as a perfect score and
        # is not even storable in a JSON column.
        profit_factor=(float(gross_profit / gross_loss) if gross_loss > 0 else None),
        average_win=float(np.mean(wins)) if wins else 0.0,
        average_loss=float(np.mean(losses)) if losses else 0.0,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        total_costs=total_costs,
    )
