"""Net Worth pillar endpoint (Chunk 9.7) — one bundled call for first paint,
like /benchmarks/compare and /portfolio/full-snapshot.
"""
from __future__ import annotations

import warnings

from fastapi import APIRouter, HTTPException, Query

from modules.finance import networth

router = APIRouter()

VALID_PERIODS = set(networth.PERIOD_DAYS)


@router.get("/networth/snapshot")
def networth_snapshot(period: str = Query("3M")) -> dict:
    """Hero donut breakdown, trend series, milestone projection and the
    CASH/PORTFOLIO accounts hierarchy, in one round-trip."""
    period = period.upper()
    if period not in VALID_PERIODS:
        raise HTTPException(status_code=422, detail=f"period must be one of {', '.join(sorted(VALID_PERIODS))}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return networth.snapshot(period)
