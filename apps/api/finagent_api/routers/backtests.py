"""Backtesting.

Every response carries the disclaimer below. A backtest is a historical simulation under
stated assumptions; it is not a prediction and not advice.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from finagent_api.deps import Db, WorkspaceContext, expensive_operation_guard, require_permission
from finagent_api.jobs.queue import get_queue
from finagent_api.rbac import Permission
from finagent_api.schemas import (
    BacktestCreateRequest,
    BacktestDetailResponse,
    BacktestResponse,
    BacktestSplitResult,
)
from finagent_api.services import backtest_service

router = APIRouter(prefix="/backtests", tags=["backtests"])

ReadBacktest = Annotated[WorkspaceContext, Depends(require_permission(Permission.BACKTEST_READ))]
RunBacktest = Annotated[WorkspaceContext, Depends(require_permission(Permission.BACKTEST_RUN))]
Expensive = Annotated[WorkspaceContext, Depends(expensive_operation_guard)]

DISCLAIMER = (
    "Historical simulation under the stated cost, slippage and execution-lag assumptions. "
    "Past simulated performance does not indicate future results and is not investment advice."
)


@router.get("", response_model=list[BacktestResponse], summary="List backtests")
def list_backtests(
    db: Db,
    context: ReadBacktest,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[BacktestResponse]:
    return [
        BacktestResponse.model_validate(row)
        for row in backtest_service.list_backtests(
            db, workspace_id=context.workspace_id, limit=limit, offset=offset
        )
    ]


@router.post(
    "",
    response_model=BacktestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Define a backtest",
)
def create_backtest(
    payload: BacktestCreateRequest, db: Db, context: RunBacktest
) -> BacktestResponse:
    draft = backtest_service.BacktestDraft(
        **payload.model_dump(exclude={"rebalance_frequency"}),
        rebalance_frequency=payload.rebalance_frequency.value,
    )
    backtest = backtest_service.create_backtest(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        draft=draft,
        user_id=context.user_id,
    )
    return BacktestResponse.model_validate(backtest)


@router.post(
    "/{backtest_id}/run",
    response_model=BacktestDetailResponse,
    summary="Execute the backtest over its train/validation/test splits",
)
def run_backtest(
    backtest_id: str, db: Db, context: RunBacktest, _guard: Expensive
) -> BacktestDetailResponse:
    backtest_service.get_backtest(
        db, workspace_id=context.workspace_id, backtest_id=backtest_id
    )
    db.commit()
    get_queue().submit("backtest.execute", backtest_id=backtest_id, user_id=context.user_id)
    db.expire_all()
    return _detail(db, context, backtest_id, include_trades=False)


@router.get(
    "/{backtest_id}",
    response_model=BacktestDetailResponse,
    summary="Backtest configuration, split results and equity curves",
)
def get_backtest(
    backtest_id: str,
    db: Db,
    context: ReadBacktest,
    include_trades: bool = Query(default=True),
) -> BacktestDetailResponse:
    return _detail(db, context, backtest_id, include_trades=include_trades)


def _detail(
    db, context: WorkspaceContext, backtest_id: str, *, include_trades: bool  # noqa: ANN001
) -> BacktestDetailResponse:
    backtest = backtest_service.get_backtest(
        db, workspace_id=context.workspace_id, backtest_id=backtest_id
    )
    detail = backtest_service.backtest_detail(db, backtest, include_trades=include_trades)
    return BacktestDetailResponse(
        backtest=BacktestResponse.model_validate(backtest),
        runs=[BacktestSplitResult.model_validate(run) for run in detail["runs"]],
        overfitting=detail.get("overfitting"),
        test_split_use_count=detail.get("test_split_use_count", 0),
        reporting_note=detail["reporting_note"],
        disclaimer=DISCLAIMER,
    )
