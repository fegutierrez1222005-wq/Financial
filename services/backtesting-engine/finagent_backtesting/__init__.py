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
    "PriceDataset",
    "BacktestResult",
    "EquityPoint",
    "Trade",
    "run_backtest",
    "BacktestMetrics",
    "compute_metrics",
    "max_drawdown",
    "BacktestSpec",
    "SplitConfig",
    "StrategyKind",
    "StrategySpec",
    "OverfittingAssessment",
    "SplitRunResult",
    "assess_overfitting",
    "default_split_config",
    "run_with_splits",
    "SignalResult",
    "generate_signal",
    "Finding",
    "FindingCode",
    "Severity",
    "ValidationReport",
    "validate_pre_run",
]
