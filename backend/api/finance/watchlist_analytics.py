"""Watchlist analytics endpoints (Phase 15d, Category I).

Scores watchlist names on the same metrics as held positions and models the
marginal effect of adding a name to the current portfolio.
"""
from __future__ import annotations

import warnings

from fastapi import APIRouter
from pydantic import BaseModel

from core.config import get_logger
from modules.finance import watchlist_analytics as wa

logger = get_logger(__name__)

router = APIRouter()


class SimulateAddRequest(BaseModel):
    ticker: str
    weight: float


@router.get("/watchlist/metrics")
def metrics() -> dict:
    """Sharpe / vol / beta / drawdown / momentum for every watchlist ticker."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rows = wa.watchlist_metrics()
    return {"metrics": rows, "count": len(rows), "beta_benchmark": wa.BETA_BENCHMARK}


@router.post("/watchlist/simulate-add")
def simulate_add(req: SimulateAddRequest) -> dict:
    """Modeled effect on the portfolio of adding ``ticker`` at ``weight``."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return wa.add_to_portfolio_simulation(req.ticker.upper(), req.weight)
