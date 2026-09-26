"""CAPM views for the workspace Performance tab (Chunk 6): Security Market Line
and return decomposition.

Both sit on :func:`optimization.capm_regression` — the same single-index
regression that produces the Optimization tab's CAPM expected returns (Chunk 3.5),
over the same window (:func:`optimization.get_returns_matrix`, 5y lookback) and
the same hardcoded risk-free rate — so a holding's beta and CAPM expected return
here are *identical* to the ones the frontier is built from.

**SML** — x = beta, y = return. The line is ``rf + beta * (E[rm] - rf)``; each
holding is plotted at (beta, actual annualized return). ``alpha`` (Jensen's) is
its vertical distance above the line: ``actual - CAPM expected``. "Actual" is the
arithmetic annualized mean daily return (mean * 252) — the same convention CAPM's
expected return uses, so the two are like-for-like.

**Decomposition** — over a chosen period, each holding's realized return splits
into ``market`` (beta x the benchmark's period return), ``alpha`` (the regression
intercept accrued over the period's trading days) and ``idiosyncratic`` (whatever
is left). Beta / alpha are estimated once on the long lookback window (stable) and
applied to the period; ``idiosyncratic`` is defined as the remainder
``actual - market - alpha`` so the three always sum exactly to ``actual``. It
therefore also absorbs compounding and estimation-window drift — it is the
"unexplained by the market model" bucket, not a pure noise term.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from core.config import BENCHMARKS, DEFAULT_BENCHMARK, DEFAULT_RISK_FREE_RATE, get_logger
from modules.finance.optimization import TRADING_DAYS, capm_regression, get_returns_matrix
from modules.finance.performance import filter_by_period
from modules.finance.positions import current_holdings
from modules.finance.price_history import get_returns

logger = get_logger(__name__)

PERIODS = ("1m", "3m", "6m", "ytd", "1y", "3y", "all")
LOOKBACK_YEARS = 5


def _bench_ticker(benchmark: str) -> str:
    return BENCHMARKS.get(benchmark, BENCHMARKS[DEFAULT_BENCHMARK])["ticker"]


def _weights(tickers: list[str]) -> dict[str, float]:
    """Market-value weights from quantity x latest *cached* close (native currency).

    Same basis the Optimization tab's current-portfolio marker uses, so weights agree
    across the two views — and it stays off the network: the EUR-converted weights on the
    Portfolio tab (dashboard.holdings_with_day_change) do per-ticker quote-currency / FX
    lookups that cost ~6s per request. Native weights differ from EUR weights only by
    cross-currency FX, which is negligible for a roll-up.
    """
    from modules.finance.price_history import latest_price

    holdings = current_holdings()
    mv = {t: holdings.get(t, 0.0) * (latest_price(t) or 0.0) for t in tickers}
    total = sum(mv.values())
    return {t: v / total for t, v in mv.items() if v > 0} if total > 0 else {}


def _resolve(tickers: Optional[list[str]]) -> list[str]:
    return list(dict.fromkeys(tickers if tickers else current_holdings().keys()))


def _market_annual_mean(market: pd.Series) -> Optional[float]:
    """E[rm] from the benchmark alone, over the same 5y lookback (used when there
    are no holdings, so the SML line can still be drawn)."""
    if market.empty:
        return None
    cutoff = market.index.max() - pd.DateOffset(years=LOOKBACK_YEARS)
    return float(market[market.index >= cutoff].mean() * TRADING_DAYS)


def _roll_up(rows: list[dict], weights: dict[str, float], keys: list[str]) -> Optional[dict]:
    """Weighted sum of ``keys`` over ``rows`` (weights renormalized to those present)."""
    w = {r["ticker"]: weights.get(r["ticker"], 0.0) for r in rows}
    total = sum(w.values())
    if total <= 0:
        return None
    return {k: sum(r[k] * w[r["ticker"]] / total for r in rows if r[k] is not None) for k in keys}


# --- Security Market Line ----------------------------------------------------------

def security_market_line(
    benchmark: str = DEFAULT_BENCHMARK,
    tickers: Optional[list[str]] = None,
    risk_free: float = DEFAULT_RISK_FREE_RATE,
) -> dict:
    """SML line + one point per holding (+ a portfolio roll-up and the market itself)."""
    tk = _resolve(tickers)
    market = get_returns(_bench_ticker(benchmark))
    base = {"benchmark": benchmark, "risk_free_rate": risk_free, "line": None, "market": None,
            "points": [], "portfolio": None, "window": None}
    if market.empty:
        return {**base, "available": False, "reason": "no benchmark price history"}

    reg, rets = None, pd.DataFrame()
    if tk:
        rets = get_returns_matrix(tk, LOOKBACK_YEARS)
        reg = capm_regression(rets, market) if not rets.empty else None
    market_mean = reg[1] * TRADING_DAYS if reg else _market_annual_mean(market)
    if market_mean is None:
        return {**base, "available": False, "reason": "no benchmark price history"}

    slope = market_mean - risk_free
    out = {
        **base,
        "available": True,
        "line": {"intercept": risk_free, "slope": slope},
        "market": {"beta": 1.0, "expected_return": market_mean},
    }
    if reg is None:
        return {**out, "reason": "no holdings" if not tk else "not enough overlapping history with the benchmark"}

    stats, _ = reg
    weights = _weights(tk)
    points = []
    for t in stats.index:
        beta = float(stats.loc[t, "beta"])
        expected = risk_free + beta * slope
        actual = float(stats.loc[t, "mean_daily"] * TRADING_DAYS)
        points.append({
            "ticker": t, "beta": beta, "expected_return_capm": expected,
            "actual_return": actual, "alpha": actual - expected, "weight": weights.get(t),
        })
    joined = rets.join(market.rename("__m__"), how="inner").dropna()
    port = _roll_up(points, weights, ["beta", "expected_return_capm", "actual_return", "alpha"])
    return {
        **out,
        "reason": None,
        "points": points,
        "portfolio": ({"ticker": "portfolio", **port} if port else None),
        "window": {"start": joined.index[0].date().isoformat(), "end": joined.index[-1].date().isoformat(), "days": len(joined)},
    }


# --- Return decomposition -------------------------------------------------------------

def _cum(returns: pd.Series) -> Optional[float]:
    return float((1 + returns).prod() - 1) if not returns.empty else None


def capm_return_decomposition(
    benchmark: str = DEFAULT_BENCHMARK,
    period: str = "1y",
    tickers: Optional[list[str]] = None,
) -> dict:
    """Per-holding ``{actual, market (beta x Rm), alpha, idiosyncratic}`` over ``period``,
    plus a current-weight roll-up. The three components sum exactly to ``actual``."""
    period = period.lower() if period.lower() in PERIODS else "1y"
    tk = _resolve(tickers)
    base = {"benchmark": benchmark, "period": period, "market_return": None, "days": 0, "rows": [], "portfolio": None}
    if not tk:
        return {**base, "available": False, "reason": "no holdings to decompose"}

    market = get_returns(_bench_ticker(benchmark))
    rets = get_returns_matrix(tk, LOOKBACK_YEARS)
    reg = capm_regression(rets, market) if not (market.empty or rets.empty) else None
    if reg is None:
        return {**base, "available": False, "reason": "not enough overlapping history with the benchmark"}
    stats, _ = reg

    m_period = filter_by_period(market, period)
    market_return = _cum(m_period)
    days = len(m_period)
    rows = []
    for t in stats.index:
        actual = _cum(filter_by_period(get_returns(t), period))
        if actual is None or market_return is None:
            continue
        beta = float(stats.loc[t, "beta"])
        market_comp = beta * market_return
        alpha = float(stats.loc[t, "alpha_daily"]) * days
        rows.append({
            "ticker": t, "beta": beta, "actual_return": actual, "market": market_comp,
            "alpha": alpha, "idiosyncratic": actual - market_comp - alpha,
        })
    if not rows:
        return {**base, "available": False, "reason": "no price history in this period", "market_return": market_return, "days": days}

    weights = _weights([r["ticker"] for r in rows])
    port = _roll_up(rows, weights, ["beta", "actual_return", "market", "alpha", "idiosyncratic"])
    return {
        **base,
        "available": True,
        "reason": None,
        "market_return": market_return,
        "days": days,
        "rows": rows,
        "portfolio": ({"ticker": "portfolio", **port} if port else None),
    }
