"""Risk analytics endpoints (Phase 15a, Category C)."""
from __future__ import annotations

import warnings

from fastapi import APIRouter, Query

from core.config import DEFAULT_RISK_FREE_RATE, DEFAULT_BENCHMARK, get_logger
from modules.finance import risk
from modules.finance.positions import current_holdings

logger = get_logger(__name__)

router = APIRouter()


@router.get("/risk")
def get_risk(benchmark: str = Query(DEFAULT_BENCHMARK), rfr: float = Query(DEFAULT_RISK_FREE_RATE, ge=0, le=0.25)) -> dict:
    """Full risk dashboard for the current portfolio (Sharpe / Sortino use ``rfr``, default 4%)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return risk.compute_all(benchmark=benchmark, risk_free=rfr)


@router.get("/risk/correlation")
def correlation(include_benchmarks: bool = Query(True)) -> dict:
    """Pairwise return correlation matrix across current holdings — and, by default, the four
    comparison benchmarks (listed first; their labels are in ``benchmarks`` so the UI can style them)."""
    tickers = list(current_holdings().keys())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        matrix = risk.correlation_matrix_with_benchmarks(tickers, include_benchmarks)
    if matrix.empty:
        return {"tickers": [], "matrix": [], "benchmarks": []}
    ordered = list(matrix.columns)
    rows = [
        {"ticker": t, **{c: round(float(matrix.loc[t, c]), 3) for c in ordered}}
        for t in ordered
    ]
    bench = [b for b in risk.benchmark_labels() if b in ordered] if include_benchmarks else []
    return {"tickers": ordered, "matrix": rows, "benchmarks": bench}
