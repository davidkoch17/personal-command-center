"""Portfolio optimization endpoints (Phase 15b, Category D)."""
from __future__ import annotations

import warnings

from fastapi import APIRouter, Query
from pydantic import BaseModel

from core.config import BENCHMARKS, DEFAULT_BENCHMARK, DEFAULT_RISK_FREE_RATE, get_logger
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
        # Chunk 3 B1 — the CML is drawn from (0, risk_free_rate) through the
        # tangency (max_sharpe) point; expose the same constant every Sharpe/
        # CAPM computation already uses rather than the frontend hardcoding it.
        "risk_free_rate": DEFAULT_RISK_FREE_RATE,
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
    risk_free: float = Query(DEFAULT_RISK_FREE_RATE),
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


# ============================================================
# Chunk 3 — constraint modal (D8) + distance-from-frontier (B2)
# ============================================================

class BoundConstraint(BaseModel):
    min: float | None = None
    max: float | None = None


class ConcentrationConstraint(BaseModel):
    max_single: float | None = None
    max_top5: float | None = None
    hhi_cap: float | None = None


class ConstraintSetRequest(BaseModel):
    """One constraint-modal submission. Each section is ``None`` when its
    toggle is off in the UI — that section is then never sent to the solver
    (see modules.finance.optimization._build_constrained_ef)."""

    tickers: list[str] | None = None
    n_points: int = 30
    bucket_caps: dict[str, BoundConstraint] | None = None
    position_bounds: dict[str, BoundConstraint] | None = None
    concentration: ConcentrationConstraint | None = None
    currency_caps: dict[str, float] | None = None
    vol_budget: dict[str, float] | None = None  # {"max_vol": <annualized fraction>}


@router.post("/optimization/frontier-with-constraints")
def frontier_with_constraints(req: ConstraintSetRequest) -> dict:
    """Constrained efficient frontier for the D8 constraint modal's preview.

    Returns only the constrained side — the frontend already holds the
    unconstrained frontier from the tab's initial ``/optimization/frontier``
    load and overlays this on top of it, so this endpoint doesn't redundantly
    recompute the unconstrained curve.
    """
    tk = opt._resolve_tickers([t.strip().upper() for t in (req.tickers or [])] or None)
    constraints = {
        "bucket_caps": {k: v.model_dump() for k, v in req.bucket_caps.items()} if req.bucket_caps else None,
        "position_bounds": {k: v.model_dump() for k, v in req.position_bounds.items()} if req.position_bounds else None,
        "concentration": req.concentration.model_dump() if req.concentration else None,
        "currency_caps": req.currency_caps,
        "vol_budget": req.vol_budget,
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mu = opt.expected_returns_mean(tk)
        S = opt.covariance_matrix(tk)
        result = opt.build_frontier_constrained(tk, mu, S, constraints, n_points=req.n_points)
    return {"tickers": tk, "constrained": result}


@router.get("/optimization/distance-from-frontier")
def distance_from_frontier(
    benchmark: str = Query(DEFAULT_BENCHMARK),
    tickers: str | None = Query(None),
) -> dict:
    """Current-portfolio Sharpe vs. the CAPM-tangency Sharpe for ``benchmark``
    (B2's distance-from-frontier callout) — see
    modules.finance.optimization.compute_distance_from_frontier for why the
    tangency here is CAPM-based rather than the main chart's historical-mean
    tangency (this is what makes the callout respond to the benchmark switch)."""
    from modules.finance.positions import current_holdings
    from modules.finance.price_history import get_returns, latest_price

    tk = _parse_tickers(tickers)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mu = opt.expected_returns_mean(tk)
        S = opt.covariance_matrix(tk)
        holdings = current_holdings()
        weights = {t: holdings.get(t, 0.0) * (latest_price(t) or 0.0) for t in tk}
        bench_ticker = BENCHMARKS.get(benchmark, BENCHMARKS[DEFAULT_BENCHMARK])["ticker"]
        bench_rets = get_returns(bench_ticker)
        result = opt.compute_distance_from_frontier(tk, weights, mu, S, bench_rets)
    return {"benchmark": benchmark, **result}
