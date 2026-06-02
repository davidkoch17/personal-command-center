"""Performance metrics endpoints (Phase 15a, Category B)."""
from __future__ import annotations

import warnings

import pandas as pd
from fastapi import APIRouter, Query

from core.config import DEFAULT_BENCHMARK, get_logger
from modules.finance import performance as perf

logger = get_logger(__name__)

router = APIRouter()


@router.get("/performance")
def performance(
    period: str = Query("ytd", pattern="^(ytd|1y|3y|5y|all)$"),
    benchmark: str = Query(DEFAULT_BENCHMARK),
) -> dict:
    """All performance metrics for the current portfolio over ``period``."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return perf.compute_all(period=period, benchmark=benchmark)


@router.get("/performance/cumulative")
def cumulative(
    period: str = Query("1y", pattern="^(ytd|1y|3y|5y|all)$"),
    benchmark: str = Query(DEFAULT_BENCHMARK),
) -> dict:
    """Cumulative-return series for the portfolio + benchmark (for the chart)."""
    from core.config import BENCHMARKS
    from modules.finance.price_history import get_returns

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        port = perf.filter_by_period(perf.portfolio_returns(), period)
        if port.empty:
            return {"period": period, "benchmark": benchmark, "series": []}
        bench_ticker = BENCHMARKS.get(benchmark, BENCHMARKS[DEFAULT_BENCHMARK])["ticker"]
        bench = get_returns(bench_ticker)
        aligned = pd.concat([port, bench], axis=1).dropna()
        aligned.columns = ["portfolio", "benchmark"]
        cum = (1 + aligned).cumprod() - 1

    series = [
        {
            "date": pd.Timestamp(idx).date().isoformat(),
            "portfolio": round(float(row["portfolio"]), 4),
            "benchmark": round(float(row["benchmark"]), 4),
        }
        for idx, row in cum.iterrows()
    ]
    return {
        "period": period,
        "benchmark": benchmark,
        "benchmark_name": BENCHMARKS.get(benchmark, {}).get("name", benchmark),
        "series": series,
    }


@router.get("/performance/rolling")
def rolling(
    window: int = Query(252, ge=20, le=756),
    benchmark: str = Query(DEFAULT_BENCHMARK),
) -> dict:
    """Rolling Sharpe / alpha / beta series over ``window`` trading days."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = perf.rolling_metrics(perf.portfolio_returns(), window_days=window, benchmark=benchmark)

    if df.empty:
        return {"window": window, "benchmark": benchmark, "series": []}

    series = [
        {
            "date": pd.Timestamp(idx).date().isoformat(),
            "sharpe": _r(row.get("sharpe")),
            "alpha": _r(row.get("alpha")),
            "beta": _r(row.get("beta")),
        }
        for idx, row in df.iterrows()
    ]
    return {"window": window, "benchmark": benchmark, "series": series}


def _r(value) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    import math
    return round(f, 4) if math.isfinite(f) else None
