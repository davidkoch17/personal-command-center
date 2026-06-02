"""Risk analytics endpoints (Phase 15a, Category C)."""
from __future__ import annotations

import warnings

from fastapi import APIRouter, Query

from core.config import DEFAULT_BENCHMARK, get_logger
from modules.finance import risk
from modules.finance.positions import current_holdings

logger = get_logger(__name__)

router = APIRouter()


@router.get("/risk")
def get_risk(benchmark: str = Query(DEFAULT_BENCHMARK)) -> dict:
    """Full risk dashboard for the current portfolio."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return risk.compute_all(benchmark=benchmark)


@router.get("/risk/correlation")
def correlation() -> dict:
    """Pairwise return correlation matrix across current holdings."""
    tickers = list(current_holdings().keys())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        matrix = risk.correlation_matrix(tickers)
    if matrix.empty:
        return {"tickers": [], "matrix": []}
    ordered = list(matrix.columns)
    rows = [
        {"ticker": t, **{c: round(float(matrix.loc[t, c]), 3) for c in ordered}}
        for t in ordered
    ]
    return {"tickers": ordered, "matrix": rows}
