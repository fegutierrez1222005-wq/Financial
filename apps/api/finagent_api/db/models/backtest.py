"""Backtest configuration, run, trade, metric and equity-curve tables."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from finagent_api.db.base import (
    Base,
    EnumString,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
    WorkspaceScopedMixin,
)
from finagent_api.db.types import GUID, JSONB, UTCDateTime


class Backtest(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, SoftDeleteMixin, Base):
    __tablename__ = "backtests"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    universe: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    strategy: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    rebalance_frequency: Mapped[str] = mapped_column(EnumString, default="monthly", nullable=False)
    transaction_cost_bps: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)
    slippage_bps: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    initial_capital: Mapped[float] = mapped_column(Float, default=10_000_000.0, nullable=False)
    max_position_weight: Mapped[float] = mapped_column(Float, default=0.25, nullable=False)
    signal_lag_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    risk_free_rate: Mapped[float] = mapped_column(Float, default=0.02, nullable=False)
    benchmark_symbol: Mapped[str | None] = mapped_column(String(32))
    split_config: Mapped[dict | None] = mapped_column(JSONB)
    information_cutoff: Mapped[date | None] = mapped_column(Date)
    data_source_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    dataset_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    #: Incremented every time the out-of-sample window is evaluated; reuse is warned about.
    test_split_use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    spec_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(GUID())
    origin_run_id: Mapped[str | None] = mapped_column(GUID(), index=True)


class BacktestRun(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "backtest_runs"

    backtest_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    split: Mapped[str] = mapped_column(EnumString, default="full", nullable=False, index=True)
    status: Mapped[str] = mapped_column(EnumString, default="QUEUED", nullable=False, index=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    metrics_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    findings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    overfitting: Mapped[dict | None] = mapped_column(JSONB)
    rebalance_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trade_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data_fingerprint: Mapped[str | None] = mapped_column(String(64))
    spec_fingerprint: Mapped[str | None] = mapped_column(String(64))
    dataset_snapshot_id: Mapped[str | None] = mapped_column(GUID())
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    triggered_by_user_id: Mapped[str | None] = mapped_column(GUID())


class BacktestTrade(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "backtest_trades"

    backtest_run_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    notional: Mapped[float] = mapped_column(Float, nullable=False)
    commission: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    slippage_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    realised_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class BacktestMetric(UUIDMixin, TimestampMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "backtest_metrics"

    backtest_run_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    split: Mapped[str] = mapped_column(EnumString, default="full", nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)


class BacktestEquityPoint(UUIDMixin, WorkspaceScopedMixin, Base):
    __tablename__ = "backtest_equity_points"

    backtest_run_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    point_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    equity: Mapped[float] = mapped_column(Float, nullable=False)
    drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    exposure_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
