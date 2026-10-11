"""Controlled backtesting engine."""

from finagent_backtesting.dataset import PriceDataset
from finagent_backtesting.engine import BacktestResult, EquityPoint, Trade, run_backtest
from finagent_backtesting.metrics import BacktestMetrics, compute_metrics, max_drawdown
from finagent_backtesting.spec import BacktestSpec, SplitConfig, StrategyKind, StrategySpec
from finagent_backtesting.splits import (
    OverfittingAssessment,
    SplitRunResult,
    assess_overfitting,
    default_split_config,
    run_with_splits,
)
from finagent_backtesting.strategies import SignalResult, generate_signal
from finagent_backtesting.validation import (
    Finding,
    FindingCode,
    Severity,
    ValidationReport,
    validate_pre_run,
)

__all__ = [
    "BacktestMetrics",
    "BacktestResult",
    "BacktestSpec",
    "EquityPoint",
    "Finding",
    "FindingCode",
    "OverfittingAssessment",
    "PriceDataset",
    "Severity",
    "SignalResult",
    "SplitConfig",
    "SplitRunResult",
    "StrategyKind",
    "StrategySpec",
    "Trade",
    "ValidationReport",
    "assess_overfitting",
    "compute_metrics",
    "default_split_config",
    "generate_signal",
    "max_drawdown",
    "run_backtest",
    "run_with_splits",
    "validate_pre_run",
]
