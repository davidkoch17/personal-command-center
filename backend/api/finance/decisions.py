"""Decision-support endpoints (Phase 15c, Category F).

Sizing, rebalancing, tax-loss harvesting, concentration alerts, and the
conviction-weighted hypothesis view. All read live holdings + the price cache via
``decision_support.current_positions_and_prices`` so the routes stay thin.
"""
from __future__ import annotations

import warnings

from fastapi import APIRouter
from pydantic import BaseModel

from core.config import get_logger
from modules.finance import decision_support as ds

logger = get_logger(__name__)

router = APIRouter()


class SizeRequest(BaseModel):
    conviction_score: int


@router.post("/decisions/size")
def size(req: SizeRequest) -> dict:
    """Map a conviction score (0-6) to a suggested position size + EUR amount."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        positions, prices = ds.current_positions_and_prices()
        pv = ds.portfolio_value(positions, prices)
        return {"portfolio_value": pv, **ds.suggested_position_size(req.conviction_score, pv)}


@router.get("/decisions/rebalance")
def rebalance() -> dict:
    """Current bucket allocations vs target + rebalancing trade suggestions."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        positions, prices = ds.current_positions_and_prices()
        pv = ds.portfolio_value(positions, prices)
        allocations = ds.bucket_allocations(positions, prices)
        recs = ds.rebalance_recommendations(allocations, pv)
    return {
        "portfolio_value": pv,
        "allocations": allocations,
        "recommendations": recs,
        "drift_tolerance": ds.BUCKET_DRIFT_TOLERANCE,
    }


@router.get("/decisions/harvest")
def harvest() -> dict:
    """Tax-loss harvest candidates (positions at a loss) + tax-saving estimates."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        positions, prices = ds.current_positions_and_prices()
        candidates = ds.harvest_candidates(positions, prices)
    return {"candidates": candidates, "count": len(candidates)}


@router.get("/decisions/alerts")
def alerts() -> dict:
    """Concentration + drift alerts vs the Section 0 position caps."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        positions, prices = ds.current_positions_and_prices()
        items = ds.concentration_alerts(positions, prices)
    return {"alerts": items, "count": len(items)}


@router.get("/decisions/hypotheses-view")
def hypotheses_view() -> dict:
    """Aggregated conviction-weighted expected return from the hypothesis tracker."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ds.conviction_weighted_view()


@router.get("/decisions/summary")
def summary() -> dict:
    """Compact counts + headline figures for the Home 'decision alerts' panel."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ds.decision_summary()
