"""Quantitative tools: backtesting and portfolio analysis.

Both run the same validated engine the platform's own backtest pages use, so an agent
cannot obtain a "cleaner" result than a human would by calling a different code path.
"""

from __future__ import annotations

import statistics
from datetime import timedelta
from typing import Any

from finagent_agent_runner.context import ToolContext
from finagent_agent_runner.tools.base import Tool, ToolPermission, ToolResult
from finagent_agent_runner.tools.market import parse_date, today_utc
from finagent_backtesting.engine import run_backtest
from finagent_backtesting.spec import BacktestSpec, StrategySpec
from finagent_backtesting.splits import default_split_config, run_with_splits
from finagent_core.errors import ToolFailedError, ValidationFailedError


class BacktestTool(Tool):
    name = "BACKTEST"
    description = (
        "Run a historical strategy simulation with transaction costs, slippage, position limits "
        "and a one-bar signal lag. Returns metrics (CAGR, Sharpe, Sortino, max drawdown, turnover, "
        "win rate, profit factor) together with validation findings such as look-ahead, "
        "survivorship and overfitting warnings. Results with blocking findings are returned as "
        "invalid and must not be reported as performance."
    )
    required_permissions = (ToolPermission.RUN_BACKTEST, ToolPermission.READ_MARKET_DATA)
    parameters = {
        "type": "object",
        "properties": {
            "universe": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string"},
            "end_date": {"type": "string"},
            "strategy": {
                "type": "string",
                "enum": [
                    "cross_sectional_momentum", "factor_rank", "equal_weight_buy_hold", "low_volatility",
                ],
                "default": "cross_sectional_momentum",
            },
            "factor": {"type": "string", "description": "Required for factor_rank."},
            "lookback_days": {"type": "integer", "minimum": 2, "maximum": 2520, "default": 126},
            "top_n": {"type": "integer", "minimum": 1, "maximum": 100, "default": 3},
            "rebalance_frequency": {
                "type": "string",
                "enum": ["daily", "weekly", "monthly", "quarterly"],
                "default": "monthly",
            },
            "transaction_cost_bps": {"type": "number", "minimum": 0, "maximum": 500, "default": 10},
            "slippage_bps": {"type": "number", "minimum": 0, "maximum": 500, "default": 5},
            "initial_capital": {"type": "number", "minimum": 1000, "default": 10000000},
            "max_position_weight": {"type": "number", "minimum": 0.01, "maximum": 1.0, "default": 0.25},
            "use_train_test_split": {"type": "boolean", "default": True},
        },
        "required": ["universe", "start_date", "end_date"],
    }

    def run(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        if context.price_loader is None:
            raise ToolFailedError("no price data loader is attached to this run")
        universe = [str(symbol).upper() for symbol in (arguments.get("universe") or [])]
        if not universe:
            raise ValidationFailedError("universe must contain at least one symbol")

        cutoff_date = context.as_of.cutoff.date() if context.as_of.cutoff else today_utc()
        end = min(parse_date(arguments.get("end_date"), cutoff_date), cutoff_date)
        start = parse_date(arguments.get("start_date"), end - timedelta(days=365 * 3))
        if end <= start:
            raise ValidationFailedError("end_date must be after start_date")

        use_splits = bool(arguments.get("use_train_test_split", True))
        spec = BacktestSpec(
            name=f"agent backtest {arguments.get('strategy', 'cross_sectional_momentum')}",
            universe=universe,
            strategy=StrategySpec(
                kind=str(arguments.get("strategy") or "cross_sectional_momentum"),
                lookback_days=int(arguments.get("lookback_days") or 126),
                top_n=int(arguments.get("top_n") or 3),
                factor=arguments.get("factor"),
            ),
            start_date=start,
            end_date=end,
            rebalance_frequency=str(arguments.get("rebalance_frequency") or "monthly"),
            transaction_cost_bps=float(arguments.get("transaction_cost_bps") or 10.0),
            slippage_bps=float(arguments.get("slippage_bps") or 5.0),
            initial_capital=float(arguments.get("initial_capital") or 10_000_000.0),
            max_position_weight=float(arguments.get("max_position_weight") or 0.25),
            split_config=default_split_config() if use_splits else None,
            information_cutoff=cutoff_date if context.as_of.is_historical else None,
        )
        dataset = context.price_loader.load(universe, start=start, end=end, as_of=context.as_of)
        context.record_usage("BACKTEST_RUN", 1.0, universe_size=len(universe), splits=use_splits)

        if use_splits:
            split_result = run_with_splits(spec, dataset)
            payload = split_result.summary()
            payload["is_valid"] = split_result.is_valid
            warnings = [
                finding["message"]
                for result in split_result.results.values()
                for finding in result.validation.as_list()
                if finding["severity"] in ("WARNING", "ERROR")
            ]
        else:
            result = run_backtest(spec, dataset)
            payload = result.summary()
            payload["is_valid"] = result.is_valid
            warnings = [
                finding["message"]
                for finding in result.validation.as_list()
                if finding["severity"] in ("WARNING", "ERROR")
            ]

        payload["spec"] = {
            "universe": universe,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "strategy": spec.strategy.model_dump(),
            "transaction_cost_bps": spec.transaction_cost_bps,
            "slippage_bps": spec.slippage_bps,
            "signal_lag_days": spec.signal_lag_days,
        }
        payload["reporting_rule"] = (
            "Report out-of-sample metrics separately from in-sample metrics. Do not present a "
            "single blended figure."
        )
        return ToolResult(payload=payload, warnings=sorted(set(warnings)))


class PortfolioAnalysisTool(Tool):
    name = "PORTFOLIO_ANALYSIS"
    description = (
        "Analyse a set of weighted positions: historical portfolio return and volatility, maximum "
        "drawdown, correlation between holdings, and concentration (Herfindahl index). Does not "
        "place orders and does not give investment advice."
    )
    required_permissions = (ToolPermission.READ_MARKET_DATA,)
    parameters = {
        "type": "object",
        "properties": {
            "positions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}, "weight": {"type": "number"}},
                },
            },
            "start_date": {"type": "string"},
            "end_date": {"type": "string"},
        },
        "required": ["positions"],
    }

    def run(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        if context.price_loader is None:
            raise ToolFailedError("no price data loader is attached to this run")
        positions: dict[str, float] = {}
        for entry in arguments.get("positions") or []:
            if isinstance(entry, dict) and entry.get("symbol"):
                positions[str(entry["symbol"]).upper()] = float(entry.get("weight") or 0.0)
        if not positions:
            raise ValidationFailedError("positions must contain at least one {symbol, weight}")
        total_weight = sum(positions.values())
        if total_weight <= 0:
            raise ValidationFailedError("position weights must sum to a positive number")

        cutoff_date = context.as_of.cutoff.date() if context.as_of.cutoff else today_utc()
        end = min(parse_date(arguments.get("end_date"), cutoff_date), cutoff_date)
        start = parse_date(arguments.get("start_date"), end - timedelta(days=365))
        dataset = context.price_loader.load(list(positions), start=start, end=end, as_of=context.as_of)
        if dataset.prices.empty:
            raise ToolFailedError("no admissible price history for the requested positions")

        returns = dataset.prices.ffill().dropna(how="all").pct_change().dropna(how="all")
        available = [symbol for symbol in positions if symbol in returns.columns]
        missing = [symbol for symbol in positions if symbol not in returns.columns]
        if not available:
            raise ToolFailedError("none of the requested symbols have price history")

        weights = {symbol: positions[symbol] / total_weight for symbol in available}
        portfolio_returns = sum(returns[symbol].fillna(0.0) * weight for symbol, weight in weights.items())
        equity = (1.0 + portfolio_returns).cumprod()
        drawdown = float(abs((equity / equity.cummax() - 1.0).min()) * 100.0) if len(equity) else 0.0
        daily = [float(value) for value in portfolio_returns.tolist() if value == value]
        volatility = statistics.stdev(daily) * (252**0.5) * 100.0 if len(daily) > 1 else 0.0

        return ToolResult(
            payload={
                "positions": weights,
                "excluded_symbols": missing,
                "window": {"start": start.isoformat(), "end": end.isoformat()},
                "total_return_pct": round((float(equity.iloc[-1]) - 1.0) * 100.0, 4) if len(equity) else 0.0,
                "annualised_volatility_pct": round(volatility, 4),
                "max_drawdown_pct": round(drawdown, 4),
                "herfindahl_index": round(sum(weight**2 for weight in weights.values()), 4),
                "largest_position_pct": round(max(weights.values()) * 100.0, 2),
                "correlations": (
                    returns[available].corr().round(4).to_dict() if len(available) > 1 else {}
                ),
                "is_demo_data": dataset.is_demo,
                "information_cutoff": context.as_of.describe(),
            },
            warnings=(
                ["Portfolio statistics were computed on labelled DEMO price data."]
                if dataset.is_demo
                else []
            ),
        )
