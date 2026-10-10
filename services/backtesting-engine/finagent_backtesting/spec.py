"""Backtest configuration objects.

Defaults are deliberately conservative: costs and slippage are non-zero and the signal lag
is one bar, because the usual way to produce a beautiful, worthless backtest is to set
those to zero.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finagent_core.schemas.enums import BacktestSplit, RebalanceFrequency


class StrategyKind(StrEnum):
    CROSS_SECTIONAL_MOMENTUM = "cross_sectional_momentum"
    FACTOR_RANK = "factor_rank"
    EQUAL_WEIGHT_BUY_HOLD = "equal_weight_buy_hold"
    LOW_VOLATILITY = "low_volatility"


class StrategySpec(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    kind: StrategyKind = StrategyKind.CROSS_SECTIONAL_MOMENTUM
    lookback_days: int = Field(default=126, ge=2, le=2520)
    top_n: int = Field(default=3, ge=1, le=500)
    factor: str | None = Field(default=None, description="Factor column for FACTOR_RANK.")
    ascending: bool = Field(default=False, description="False ranks the highest values first.")
    skip_recent_days: int = Field(default=0, ge=0, le=60, description="Momentum reversal buffer.")
    params: dict[str, Any] = Field(default_factory=dict)


class SplitConfig(BaseModel):
    """Sequential train / validation / out-of-sample split.

    Sequential, not random: shuffling a time series leaks the future into the past.
    """

    train_pct: float = Field(default=0.5, gt=0.0, lt=1.0)
    validation_pct: float = Field(default=0.25, gt=0.0, lt=1.0)
    test_pct: float = Field(default=0.25, gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def _sums_to_one(self) -> SplitConfig:
        if abs(self.train_pct + self.validation_pct + self.test_pct - 1.0) > 1e-6:
            raise ValueError("train/validation/test percentages must sum to 1.0")
        return self


class BacktestSpec(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    name: str = "Untitled backtest"
    universe: list[str] = Field(min_length=1)
    strategy: StrategySpec = Field(default_factory=StrategySpec)
    start_date: date
    end_date: date
    rebalance_frequency: RebalanceFrequency = RebalanceFrequency.MONTHLY
    transaction_cost_bps: float = Field(default=10.0, ge=0.0, le=1000.0)
    slippage_bps: float = Field(default=5.0, ge=0.0, le=1000.0)
    initial_capital: float = Field(default=10_000_000.0, gt=0.0)
    max_position_weight: float = Field(default=0.25, gt=0.0, le=1.0)
    min_cash_buffer: float = Field(default=0.0, ge=0.0, lt=1.0)
    #: Bars of delay between signal observation and execution. 0 is look-ahead.
    signal_lag_days: int = Field(default=1, ge=0, le=30)
    risk_free_rate: float = Field(default=0.02, ge=-0.05, le=0.25)
    benchmark_symbol: str | None = None
    split_config: SplitConfig | None = None
    allow_short: bool = Field(default=False, description="V1 is long-only.")
    information_cutoff: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _validate_window(self) -> BacktestSpec:
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        if self.allow_short:
            raise ValueError("short selling is not supported in this version")
        if self.strategy.kind == StrategyKind.FACTOR_RANK and not self.strategy.factor:
            raise ValueError("FACTOR_RANK strategies require a factor name")
        return self

    def fingerprint(self) -> str:
        """Stable hash of the configuration — half of a reproducibility key."""
        payload = json.loads(self.model_dump_json())
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def window_for(self, split: BacktestSplit) -> tuple[date, date]:
        """Date window for a split. Windows are contiguous and non-overlapping."""
        if split is BacktestSplit.FULL or self.split_config is None:
            return self.start_date, self.end_date
        total_days = (self.end_date - self.start_date).days
        config = self.split_config
        train_end = self.start_date + timedelta(days=int(total_days * config.train_pct))
        validation_end = train_end + timedelta(days=int(total_days * config.validation_pct))
        if split is BacktestSplit.TRAIN:
            return self.start_date, train_end
        if split is BacktestSplit.VALIDATION:
            return train_end + timedelta(days=1), validation_end
        return validation_end + timedelta(days=1), self.end_date
