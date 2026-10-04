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


def _bench_ticker(benchmark: str) -> str:
    """Benchmark key (MSCI_WORLD, SPY, ...) -> the yfinance ticker whose returns
    stand in for "the market" in the CAPM expected-return vector."""
    return BENCHMARKS.get(benchmark, BENCHMARKS[DEFAULT_BENCHMARK])["ticker"]


@router.get("/optimization/frontier")
def frontier(
    tickers: str | None = Query(None),
    n_points: int = Query(50, ge=5, le=200),
    benchmark: str = Query(DEFAULT_BENCHMARK),
    rfr: float = Query(DEFAULT_RISK_FREE_RATE, ge=0, le=0.25),
) -> dict:
    """Efficient frontier points (risk, return, sharpe, weights).

    Expected returns are CAPM-implied against ``benchmark``, so the whole curve
    (and the star / diamond / current markers) is benchmark-dependent.
    """
    tk = _parse_tickers(tickers)
    bt = _bench_ticker(benchmark)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        points = opt.efficient_frontier_points(tk, n_points=n_points, benchmark_ticker=bt, risk_free=rfr)
        max_sharpe = opt.max_sharpe_portfolio(tk, rfr, benchmark_ticker=bt)
        min_var = opt.min_variance_portfolio(tk, benchmark_ticker=bt, risk_free=rfr)
        current = opt.current_portfolio_point(tk, benchmark_ticker=bt, risk_free=rfr)
    return {
        "tickers": tk,
        "benchmark": benchmark,
        "points": points,
        "max_sharpe": max_sharpe,
        "min_variance": min_var,
        "current": current,
        # Chunk 3 B1 — the CML is drawn from (0, risk_free_rate) through the
        # tangency (max_sharpe) point; expose the same constant every Sharpe/
        # CAPM computation already uses rather than the frontend hardcoding it.
        "risk_free_rate": rfr,
    }


@router.get("/optimization/min-variance")
def min_variance(
    tickers: str | None = Query(None),
    max_position: float | None = Query(None, ge=0, le=1),
    min_position: float | None = Query(None, ge=0, le=1),
    benchmark: str = Query(DEFAULT_BENCHMARK),
    rfr: float = Query(DEFAULT_RISK_FREE_RATE, ge=0, le=0.25),
) -> dict:
    tk = _parse_tickers(tickers)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = opt.min_variance_portfolio(
            tk, _constraints(max_position, min_position), benchmark_ticker=_bench_ticker(benchmark), risk_free=rfr
        )
    return {"tickers": tk, "benchmark": benchmark, **result}


@router.get("/optimization/max-sharpe")
def max_sharpe(
    tickers: str | None = Query(None),
    risk_free: float = Query(DEFAULT_RISK_FREE_RATE),
    max_position: float | None = Query(None, ge=0, le=1),
    min_position: float | None = Query(None, ge=0, le=1),
    benchmark: str = Query(DEFAULT_BENCHMARK),
) -> dict:
    tk = _parse_tickers(tickers)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = opt.max_sharpe_portfolio(
            tk, risk_free, _constraints(max_position, min_position), benchmark_ticker=_bench_ticker(benchmark)
        )
    return {"tickers": tk, "benchmark": benchmark, **result}


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
    rfr: float = DEFAULT_RISK_FREE_RATE  # Chunk 9 — the Chunk 8 leftover (shared useRiskFreeRate)


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
            tk, market_caps=req.market_caps, views=views, risk_aversion=req.risk_aversion,
            risk_free=req.rfr,
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
    rfr: float = DEFAULT_RISK_FREE_RATE  # risk-free rate for CAPM mu + Sharpe (shared useRiskFreeRate)
    benchmark: str = DEFAULT_BENCHMARK  # CAPM market for mu — must match the base frontier's
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
        # Same CAPM (mu, S) the unconstrained /frontier is built from, so the
        # overlay and the base curve differ only by the constraints.
        mu, S = opt.mu_cov(tk, _bench_ticker(req.benchmark), req.rfr)
        # Positional constraints index by mu's order — use the tickers that survived.
        result = opt.build_frontier_constrained(list(mu.index), mu, S, constraints, n_points=req.n_points, risk_free=req.rfr)
    return {"tickers": list(mu.index), "benchmark": req.benchmark, "constrained": result}


@router.get("/optimization/distance-from-frontier")
def distance_from_frontier(
    benchmark: str = Query(DEFAULT_BENCHMARK),
    tickers: str | None = Query(None),
    rfr: float = Query(DEFAULT_RISK_FREE_RATE, ge=0, le=0.25),
) -> dict:
    """Current-portfolio Sharpe vs. the tangency Sharpe (B2's callout).

    Uses the exact (mu, S) that ``/frontier`` plots for ``benchmark`` — CAPM
    expected returns — so this tangency Sharpe equals the chart star's Sharpe.
    """
    from modules.finance.positions import current_holdings
    from modules.finance.price_history import latest_price

    tk = _parse_tickers(tickers)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mu, S = opt.mu_cov(tk, _bench_ticker(benchmark), rfr)
        holdings = current_holdings()
        weights = {t: holdings.get(t, 0.0) * (latest_price(t) or 0.0) for t in tk}
        result = opt.compute_distance_from_frontier(tk, weights, mu, S, rfr)
    return {"benchmark": benchmark, **result}
