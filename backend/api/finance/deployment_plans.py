"""Deployment-plan (50/30/20 tranche tracker) endpoints — Chunk 6, item C6."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

from core.config import get_logger
from modules.finance import deployment_plans as dp

logger = get_logger(__name__)

router = APIRouter()

_ID = Path(..., pattern=r"^[A-Za-z0-9][A-Za-z0-9\-_.]{0,80}$")


def _raise(exc: dp.PlanError) -> None:
    """Domain errors -> HTTP: unknown plan/tranche is 404, a rule violation is 422."""
    raise HTTPException(status_code=404 if isinstance(exc, dp.NotFound) else 422, detail=str(exc))


class TrancheIn(BaseModel):
    pct: float
    target_date: date


class CreatePlanRequest(BaseModel):
    name: str
    total_eur: float
    target_bucket: Optional[dp.Bucket] = None
    target_ticker: Optional[str] = None
    schedule: Optional[list[TrancheIn]] = None  # omitted -> 50/30/20 at now / +4w / +9w


class PatchPlanRequest(BaseModel):
    name: Optional[str] = None
    total_eur: Optional[float] = None
    target_bucket: Optional[dp.Bucket] = None
    target_ticker: Optional[str] = None
    status: Optional[dp.Status] = None
    tranche_dates: Optional[dict[int, date]] = None


class ExecuteRequest(BaseModel):
    amount_eur: float
    executed_date: Optional[date] = None
    trade_id: Optional[str] = None


@router.get("/deployment-plans")
def list_deployment_plans(status: Optional[str] = Query(None, pattern="^(in_progress|complete|cancelled)$")) -> dict:
    """Plans (optionally one status) with per-plan progress + the dashboard roll-up.

    The summary always covers *all* plans so the "active" badge doesn't change
    with the filter.
    """
    plans = dp.list_plans(status)
    return {
        "plans": [dp.with_progress(p) for p in plans],
        "summary": dp.progress_summary(dp.list_plans()),
    }


@router.post("/deployment-plans")
def create_deployment_plan(req: CreatePlanRequest) -> dict:
    try:
        plan = dp.create_plan(
            req.name, req.total_eur, req.target_bucket, req.target_ticker,
            [t.model_dump() for t in req.schedule] if req.schedule else None,
        )
    except dp.PlanError as exc:
        _raise(exc)
    return dp.with_progress(plan)


@router.get("/deployment-plans/{plan_id}")
def get_deployment_plan(plan_id: str = _ID) -> dict:
    try:
        return dp.with_progress(dp.get_plan(plan_id))
    except dp.PlanError as exc:
        _raise(exc)


@router.patch("/deployment-plans/{plan_id}")
def patch_deployment_plan(req: PatchPlanRequest, plan_id: str = _ID) -> dict:
    # Only fields the client actually sent change (so null can clear a target).
    patch = req.model_dump(exclude_unset=True)
    if "tranche_dates" in patch:
        patch["tranche_dates"] = {str(k): v for k, v in patch["tranche_dates"].items()}
    try:
        return dp.with_progress(dp.update_plan(plan_id, patch))
    except dp.PlanError as exc:
        _raise(exc)


@router.post("/deployment-plans/{plan_id}/tranches/{index}/execute")
def execute_tranche(req: ExecuteRequest, plan_id: str = _ID, index: int = Path(..., ge=0)) -> dict:
    try:
        plan = dp.mark_tranche_executed(plan_id, index, req.amount_eur, req.executed_date, req.trade_id)
    except dp.PlanError as exc:
        _raise(exc)
    return dp.with_progress(plan)


@router.delete("/deployment-plans/{plan_id}")
def delete_deployment_plan(plan_id: str = _ID) -> dict:
    try:
        dp.delete_plan(plan_id)
    except dp.PlanError as exc:
        _raise(exc)
    return {"ok": True, "id": plan_id}
