"""Portfolio Hub "Portfolio"-tab endpoints (Chunk 2).

Two thin routes over modules.finance.dashboard: the KPI-band + top-holdings
bundle (one round trip for first paint) and the indexed performance chart
series. Both take the same ``benchmark`` query param as the rest of the
finance API (default DEFAULT_BENCHMARK) so they follow the Risk tab's shared
Comparison-benchmark selection (see frontend useBenchmark, Chunk 1 Item A2).
"""
from __future__ import annotations

import warnings

from fastapi import APIRouter, Query

from core.config import DEFAULT_BENCHMARK, get_logger
from modules.finance import dashboard

logger = get_logger(__name__)

router = APIRouter()


@router.get("/dashboard/summary")
def dashboard_summary(benchmark: str = Query(DEFAULT_BENCHMARK)) -> dict:
    """KPI band (value/day-delta, YTD, Sharpe, worst-drift bucket) + top-5 holdings."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return dashboard.summary(benchmark=benchmark)


@router.get("/dashboard/performance-indexed")
def dashboard_performance_indexed(
    period: str = Query("1w", pattern="^(1d|1w|1m|ytd|1y|all)$"),
    benchmark: str = Query(DEFAULT_BENCHMARK),
) -> dict:
    """Portfolio + benchmark value, both indexed to 100 at the start of ``period``."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return dashboard.indexed_performance(period=period, benchmark=benchmark)
