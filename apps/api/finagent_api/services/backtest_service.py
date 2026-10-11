"""Backtest orchestration and persistence.

The out-of-sample window is treated as a scarce resource: every evaluation of it increments
``test_split_use_count``, and the validator warns once it has been used before. That counter
is the difference between an out-of-sample test and a second validation set.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from finagent_api.db.models import (
    Backtest,
    BacktestEquityPoint,
    BacktestMetric,
    BacktestRun,
    BacktestTrade,
)
from finagent_api.services.audit import AuditAction, record_audit
from finagent_api.services.price_loader import DbPriceLoader
from finagent_api.services.usage_service import enforce_quota, record_usage
from finagent_backtesting.engine import BacktestResult, run_backtest
from finagent_backtesting.spec import BacktestSpec, SplitConfig, StrategySpec
from finagent_backtesting.splits import default_split_config, run_with_splits
from finagent_core.cutoff import AsOfContext
from finagent_core.errors import NotFoundError, ValidationFailedError
from finagent_core.logging import get_logger, log_context
from finagent_core.schemas.enums import BacktestSplit, RunStatus, UsageKind

logger = get_logger(__name__)

MAX_EQUITY_POINTS_STORED = 4_000


@dataclass
class BacktestDraft:
    name: str
    universe: list[str]
    start_date: date
    end_date: date
    strategy_kind: str = "cross_sectional_momentum"
    factor: str | None = None
    lookback_days: int = 126
    top_n: int = 3
    rebalance_frequency: str = "monthly"
    transaction_cost_bps: float = 10.0
    slippage_bps: float = 5.0
    initial_capital: float = 10_000_000.0
    max_position_weight: float = 0.25
    signal_lag_days: int = 1
    risk_free_rate: float = 0.02
    benchmark_symbol: str | None = None
    use_splits: bool = True
    information_cutoff: date | None = None
    description: str | None = None
    origin_run_id: str | None = None


def _to_spec(draft: BacktestDraft) -> BacktestSpec:
    return BacktestSpec(
        name=draft.name,
        universe=[symbol.upper() for symbol in draft.universe],
        strategy=StrategySpec(
            kind=draft.strategy_kind,
            lookback_days=draft.lookback_days,
            top_n=draft.top_n,
            factor=draft.factor,
        ),
        start_date=draft.start_date,
        end_date=draft.end_date,
        rebalance_frequency=draft.rebalance_frequency,
        transaction_cost_bps=draft.transaction_cost_bps,
        slippage_bps=draft.slippage_bps,
        initial_capital=draft.initial_capital,
        max_position_weight=draft.max_position_weight,
        signal_lag_days=draft.signal_lag_days,
        risk_free_rate=draft.risk_free_rate,
        benchmark_symbol=draft.benchmark_symbol,
        split_config=default_split_config() if draft.use_splits else None,
        information_cutoff=draft.information_cutoff,
    )


def create_backtest(
    db: DbSession, *, organization_id: str, workspace_id: str, draft: BacktestDraft, user_id: str | None
) -> Backtest:
    if not draft.universe:
        raise ValidationFailedError("a backtest needs at least one symbol in its universe")
    spec = _to_spec(draft)

    backtest = Backtest(
        organization_id=organization_id,
        workspace_id=workspace_id,
        name=draft.name.strip() or "Untitled backtest",
        description=draft.description,
        universe=[symbol.upper() for symbol in draft.universe],
        strategy=spec.strategy.model_dump(),
        start_date=draft.start_date,
        end_date=draft.end_date,
        rebalance_frequency=draft.rebalance_frequency,
        transaction_cost_bps=draft.transaction_cost_bps,
        slippage_bps=draft.slippage_bps,
        initial_capital=draft.initial_capital,
        max_position_weight=draft.max_position_weight,
        signal_lag_days=draft.signal_lag_days,
        risk_free_rate=draft.risk_free_rate,
        benchmark_symbol=draft.benchmark_symbol,
        split_config=(spec.split_config.model_dump() if spec.split_config else None),
        information_cutoff=draft.information_cutoff,
        spec_fingerprint=spec.fingerprint(),
        created_by_user_id=user_id,
        origin_run_id=draft.origin_run_id,
    )
    db.add(backtest)
    db.flush()
    record_audit(
        db,
        action=AuditAction.BACKTEST_CREATED,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        resource_type="backtest",
        resource_id=backtest.id,
        metadata={
            "universe_size": len(backtest.universe),
            "strategy": backtest.strategy.get("kind"),
            "splits": bool(backtest.split_config),
        },
    )
    return backtest


def spec_from_row(backtest: Backtest) -> BacktestSpec:
    return BacktestSpec(
        name=backtest.name,
        universe=list(backtest.universe),
        strategy=StrategySpec(**(backtest.strategy or {})),
        start_date=backtest.start_date,
        end_date=backtest.end_date,
        rebalance_frequency=backtest.rebalance_frequency,
        transaction_cost_bps=backtest.transaction_cost_bps,
        slippage_bps=backtest.slippage_bps,
        initial_capital=backtest.initial_capital,
        max_position_weight=backtest.max_position_weight,
        signal_lag_days=backtest.signal_lag_days,
        risk_free_rate=backtest.risk_free_rate,
        benchmark_symbol=backtest.benchmark_symbol,
        split_config=SplitConfig(**backtest.split_config) if backtest.split_config else None,
        information_cutoff=backtest.information_cutoff,
    )


def execute_backtest(db: DbSession, *, backtest_id: str, user_id: str | None = None) -> list[BacktestRun]:
    """Run the configuration (full window plus splits) and persist every artefact."""
    backtest = db.get(Backtest, backtest_id)
    if backtest is None or backtest.deleted_at is not None:
        raise NotFoundError("backtest not found")
    enforce_quota(db, organization_id=backtest.organization_id, kind=UsageKind.BACKTEST_RUN)

    spec = spec_from_row(backtest)
    as_of = (
        AsOfContext.at(backtest.information_cutoff, strict=False)
        if backtest.information_cutoff
        else AsOfContext.live()
    )
    started = time.perf_counter()

    with log_context(backtest_id=backtest.id, workspace_id=backtest.workspace_id):
        dataset = DbPriceLoader(db, workspace_id=backtest.workspace_id).load(
            spec.universe, start=spec.start_date, end=spec.end_date, as_of=as_of
        )
        if spec.split_config is not None:
            outcome = run_with_splits(spec, dataset, test_split_use_count=backtest.test_split_use_count)
            results = outcome.results
            overfitting = outcome.overfitting.as_dict() if outcome.overfitting else None
            backtest.test_split_use_count += 1
        else:
            results = {BacktestSplit.FULL.value: run_backtest(spec, dataset)}
            overfitting = None

        rows = [
            _persist_result(
                db,
                backtest=backtest,
                split=split_name,
                result=result,
                overfitting=overfitting if split_name == BacktestSplit.FULL.value else None,
                user_id=user_id,
            )
            for split_name, result in results.items()
        ]

    duration_ms = int((time.perf_counter() - started) * 1000)
    for row in rows:
        row.duration_ms = duration_ms
    db.flush()

    record_usage(
        db,
        organization_id=backtest.organization_id,
        workspace_id=backtest.workspace_id,
        user_id=user_id,
        kind=UsageKind.BACKTEST_RUN,
        quantity=float(len(rows)),
        backtest_run_id=rows[0].id if rows else None,
        detail={"splits": [row.split for row in rows]},
    )
    record_audit(
        db,
        action=AuditAction.BACKTEST_RUN_COMPLETED,
        organization_id=backtest.organization_id,
        workspace_id=backtest.workspace_id,
        user_id=user_id,
        resource_type="backtest",
        resource_id=backtest.id,
        metadata={
            "splits": {row.split: row.is_valid for row in rows},
            "test_split_use_count": backtest.test_split_use_count,
        },
    )
    return rows


def _persist_result(
    db: DbSession,
    *,
    backtest: Backtest,
    split: str,
    result: BacktestResult,
    overfitting: dict[str, Any] | None,
    user_id: str | None,
) -> BacktestRun:
    run = BacktestRun(
        organization_id=backtest.organization_id,
        workspace_id=backtest.workspace_id,
        backtest_id=backtest.id,
        split=split,
        status=RunStatus.SUCCEEDED.value if result.is_valid else RunStatus.FAILED.value,
        is_valid=result.is_valid,
        start_date=result.start_date,
        end_date=result.end_date,
        metrics_summary=result.metrics.as_dict(),
        findings=result.validation.as_list(),
        overfitting=overfitting,
        rebalance_count=result.rebalance_count,
        trade_count=len(result.trades),
        is_demo_data=result.is_demo_data,
        data_fingerprint=result.data_fingerprint,
        spec_fingerprint=result.spec_fingerprint,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        error_code=None if result.is_valid else "BACKTEST_INVALID",
        error_message=(
            None
            if result.is_valid
            else "; ".join(finding.message for finding in result.validation.errors)[:2000]
        ),
        triggered_by_user_id=user_id,
    )
    db.add(run)
    db.flush()

    for name, value in result.metrics.as_dict().items():
        if value is None or value != value or value in (float("inf"), float("-inf")):
            continue
        db.add(
            BacktestMetric(
                organization_id=backtest.organization_id,
                workspace_id=backtest.workspace_id,
                backtest_run_id=run.id,
                split=split,
                name=name,
                value=float(value),
            )
        )

    for trade in result.trades:
        db.add(
            BacktestTrade(
                organization_id=backtest.organization_id,
                workspace_id=backtest.workspace_id,
                backtest_run_id=run.id,
                trade_date=trade.trade_date,
                symbol=trade.symbol,
                side=trade.side,
                quantity=trade.quantity,
                price=trade.price,
                notional=trade.notional,
                commission=trade.commission,
                slippage_cost=trade.slippage_cost,
                realised_pnl=trade.realised_pnl,
            )
        )

    points = result.equity_curve
    stride = max(1, len(points) // MAX_EQUITY_POINTS_STORED)
    for point in points[::stride]:
        db.add(
            BacktestEquityPoint(
                organization_id=backtest.organization_id,
                workspace_id=backtest.workspace_id,
                backtest_run_id=run.id,
                point_date=point.point_date,
                equity=point.equity,
                drawdown_pct=point.drawdown_pct,
                exposure_pct=point.exposure_pct,
            )
        )
    db.flush()
    return run


def get_backtest(db: DbSession, *, workspace_id: str, backtest_id: str) -> Backtest:
    backtest = db.get(Backtest, backtest_id)
    if backtest is None or backtest.workspace_id != workspace_id or backtest.deleted_at is not None:
        raise NotFoundError("backtest not found")
    return backtest


def list_backtests(db: DbSession, *, workspace_id: str, limit: int = 50, offset: int = 0) -> list[Backtest]:
    return list(
        db.scalars(
            select(Backtest)
            .where(Backtest.workspace_id == workspace_id, Backtest.deleted_at.is_(None))
            .order_by(Backtest.created_at.desc())
            .limit(min(limit, 200))
            .offset(offset)
        )
    )


def backtest_detail(db: DbSession, backtest: Backtest, *, include_trades: bool = True) -> dict[str, Any]:
    runs = list(
        db.scalars(
            select(BacktestRun)
            .where(BacktestRun.backtest_id == backtest.id)
            .order_by(BacktestRun.created_at.desc())
        )
    )
    latest_by_split: dict[str, BacktestRun] = {}
    for run in runs:
        latest_by_split.setdefault(run.split, run)

    detail: dict[str, Any] = {"runs": [], "overfitting": None}
    for split, run in latest_by_split.items():
        equity = list(
            db.scalars(
                select(BacktestEquityPoint)
                .where(BacktestEquityPoint.backtest_run_id == run.id)
                .order_by(BacktestEquityPoint.point_date)
            )
        )
        trades = (
            list(
                db.scalars(
                    select(BacktestTrade)
                    .where(BacktestTrade.backtest_run_id == run.id)
                    .order_by(BacktestTrade.trade_date)
                    .limit(500)
                )
            )
            if include_trades
            else []
        )
        detail["runs"].append(
            {
                "id": run.id,
                "split": split,
                "status": run.status,
                "is_valid": run.is_valid,
                "start_date": run.start_date.isoformat() if run.start_date else None,
                "end_date": run.end_date.isoformat() if run.end_date else None,
                "metrics": run.metrics_summary,
                "findings": run.findings,
                "rebalance_count": run.rebalance_count,
                "trade_count": run.trade_count,
                "is_demo_data": run.is_demo_data,
                "data_fingerprint": run.data_fingerprint,
                "equity_curve": [
                    {
                        "date": point.point_date.isoformat(),
                        "equity": round(point.equity, 2),
                        "drawdown_pct": round(point.drawdown_pct, 3),
                        "exposure_pct": round(point.exposure_pct, 2),
                    }
                    for point in equity
                ],
                "trades": [
                    {
                        "date": trade.trade_date.isoformat(),
                        "symbol": trade.symbol,
                        "side": trade.side,
                        "quantity": round(trade.quantity, 4),
                        "price": round(trade.price, 4),
                        "notional": round(trade.notional, 2),
                        "commission": round(trade.commission, 2),
                        "slippage_cost": round(trade.slippage_cost, 2),
                        "realised_pnl": round(trade.realised_pnl, 2),
                    }
                    for trade in trades
                ],
            }
        )
        if run.overfitting:
            detail["overfitting"] = run.overfitting

    order = {"full": 0, "train": 1, "validation": 2, "test": 3}
    detail["runs"].sort(key=lambda item: order.get(item["split"], 9))
    detail["test_split_use_count"] = backtest.test_split_use_count
    detail["reporting_note"] = (
        "In-sample, validation and out-of-sample results are reported separately and are never "
        "averaged. Repeated use of the out-of-sample window degrades its meaning."
    )
    return detail
