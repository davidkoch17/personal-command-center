"""Portfolio optimization endpoints (Phase 15b, Category D)."""
from __future__ import annotations

import warnings

from fastapi import APIRouter, Query
from pydantic import BaseModel

from core.config import get_logger
from modules.finance import optimization as opt

logger = get_logger(__name__)

router = APIRouter()


def _parse_tickers(tickers: str | None) -> list[str]:
    """Comma-separated query param -> ticker list (defaults to holdings)."""
    requested = [t.strip().upper() for t in tickers.split(",")] if tickers else None
    return opt._resolve_tickers([t for t in (requested or []) if t] or None)


def _constraints(max_position: float | None, min_position: float | None) -> dict | None:
    c: dict = {}
    if max_position is not None:
        c["max_position"] = max_position
    if min_position is not None:
        c["min_position"] = min_position
    return c or None


@router.get("/optimization/frontier")
def frontier(
    tickers: str | None = Query(None),
    n_points: int = Query(50, ge=5, le=200),
) -> dict:
    """Efficient frontier points (risk, return, sharpe, weights)."""
    tk = _parse_tickers(tickers)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        points = opt.efficient_frontier_points(tk, n_points=n_points)
        max_sharpe = opt.max_sharpe_portfolio(tk)
        min_var = opt.min_variance_portfolio(tk)
        current = opt.current_portfolio_point(tk)
    return {
        "tickers": tk,
        "points": points,
        "max_sharpe": max_sharpe,
        "min_variance": min_var,
        "current": current,
    }


@router.get("/optimization/min-variance")
def min_variance(
    tickers: str | None = Query(None),
    max_position: float | None = Query(None, ge=0, le=1),
    min_position: float | None = Query(None, ge=0, le=1),
) -> dict:
    tk = _parse_tickers(tickers)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = opt.min_variance_portfolio(tk, _constraints(max_position, min_position))
    return {"tickers": tk, **result}


@router.get("/optimization/max-sharpe")
def max_sharpe(
    tickers: str | None = Query(None),
    risk_free: float = Query(0.04),
    max_position: float | None = Query(None, ge=0, le=1),
    min_position: float | None = Query(None, ge=0, le=1),
) -> dict:
    tk = _parse_tickers(tickers)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = opt.max_sharpe_portfolio(tk, risk_free, _constraints(max_position, min_position))
    return {"tickers": tk, **result}


@router.get("/optimization/risk-parity")
def risk_parity(tickers: str | None = Query(None)) -> dict:
    tk = _parse_tickers(tickers)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        weights = opt.risk_parity_weights(tk)
    return {"tickers": tk, "weights": weights}


class BlackLittermanRequest(BaseModel):
    tickers: list[str] | None = None
    # Explicit views override the auto-pulled hypotheses when provided.
    views: list[dict] | None = None
    risk_aversion: float = 2.5
    market_caps: dict[str, float] | None = None


@router.post("/optimization/black-litterman")
def black_litterman(req: BlackLittermanRequest) -> dict:
    """Black-Litterman optimization.

    Views come from the request body when supplied, else are auto-pulled from
    ``Hypothesis_Tracker.md``.
    """
    tk = opt._resolve_tickers([t.strip().upper() for t in (req.tickers or [])] or None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        views = req.views if req.views is not None else opt.hypotheses_as_views()
        result = opt.black_litterman_with_hypotheses(
            tk, market_caps=req.market_caps, views=views, risk_aversion=req.risk_aversion
        )
    return {"tickers": tk, "auto_views": req.views is None, **result}


@router.get("/optimization/signals")
def signals() -> dict:
    """Current-vs-optimal summary for the Home 'optimization signals' block."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return opt.optimization_signals()
