"""Benchmarks tab endpoint (Chunk 5) — one bundled call, like /dashboard/summary."""
from __future__ import annotations

import warnings

from fastapi import APIRouter, HTTPException, Query

from core.config import get_logger
from modules.finance import benchmarks

logger = get_logger(__name__)

router = APIRouter()


@router.get("/benchmarks/compare")
def benchmarks_compare(period: str = Query(benchmarks.DEFAULT_PERIOD)) -> dict:
    """Metrics (return / vol / Sharpe / correlation-to-MSCI), the correlation matrix
    and the indexed-to-100 series for MSCI World, S&P 500, DAX 40 and STOXX 600 over
    ``period`` (1m/3m/6m/ytd/1y/3y/all, case-insensitive)."""
    if period.lower() not in benchmarks.PERIODS:
        raise HTTPException(status_code=422, detail=f"period must be one of {', '.join(benchmarks.PERIODS)}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return benchmarks.compare(period)
