"""Portfolio performance metrics (Phase 15a, Category B).

Builds a daily portfolio return series from current holdings + cached price
history, then layers the must-have performance measures on top: time-weighted
return, money-weighted (IRR) return, alpha / beta / tracking error / information
ratio vs a benchmark, per-position contribution, win rate, best/worst periods,
and rolling alpha/beta/Sharpe.

Returns are computed in the price series' native terms (mostly USD on yfinance)
weighted by current market value — a deliberate simplification for this
foundation phase; multi-currency decomposition is a later phase.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import empyrical as ep
import numpy as np
import pandas as pd

from core.config import BENCHMARKS, DEFAULT_BENCHMARK, get_logger
from modules.finance.positions import current_holdings, list_transactions
from modules.finance.price_history import get_closes, get_returns

logger = get_logger(__name__)

TRADING_DAYS = 252

_PERIOD_DAYS = {"1y": 365, "3y": 365 * 3, "5y": 365 * 5}


# --- Portfolio return series ------------------------------------------------

def holdings_value_series(holdings: Optional[dict] = None) -> pd.Series:
    """Daily portfolio market-value series from holdings × cached closes.

    Uses *static* current weights (today's quantities held across all history).
    Tickers with no price data are skipped. Empty Series if nothing resolves.
    """
    holdings = current_holdings() if holdings is None else holdings
    cols: dict[str, pd.Series] = {}
    for ticker, qty in holdings.items():
        closes = get_closes(ticker)
        if closes.empty:
            logger.warning("No price history for %s; excluded from return series", ticker)
            continue
        cols[ticker] = closes * qty
    if not cols:
        return pd.Series(dtype="float64")
    frame = pd.DataFrame(cols).sort_index()
    # Align on a common business-day grid and forward-fill stale prices so a
    # missing day for one ticker doesn't blank the whole portfolio value.
    frame = frame.ffill().dropna(how="all")
    return frame.sum(axis=1, min_count=1).dropna()


def portfolio_returns(holdings: Optional[dict] = None, start_date: Optional[date] = None) -> pd.Series:
    """Daily simple returns of the (static-weight) portfolio value series."""
    values = holdings_value_series(holdings)
    if values.empty:
        return pd.Series(dtype="float64")
    if start_date is not None:
        values = values[values.index.date >= start_date]
    return values.pct_change().dropna()


def filter_by_period(returns: pd.Series, period: str = "ytd") -> pd.Series:
    """Slice a daily return series to a named period.

    Periods: ``ytd``, ``1y``, ``3y``, ``5y``, ``all``.
    """
    if returns.empty:
        return returns
    last = pd.Timestamp(returns.index.max())
    period = (period or "ytd").lower()
    if period == "all":
        return returns
    if period == "ytd":
        start = pd.Timestamp(year=last.year, month=1, day=1)
    else:
        days = _PERIOD_DAYS.get(period, 365)
        start = last - timedelta(days=days)
    return returns[returns.index >= start]


# --- Core metrics -----------------------------------------------------------

def time_weighted_return(returns: pd.Series, period: str = "ytd") -> Optional[float]:
    """Cumulative (geometric) return over the period — the TWR."""
    sliced = filter_by_period(returns, period)
    if sliced.empty:
        return None
    return float(ep.cum_returns_final(sliced))


def _xirr(cashflows: list[tuple[date, float]], guess: float = 0.1) -> Optional[float]:
    """Annualized IRR for irregularly-timed cash flows (XIRR), via bisection.

    ``cashflows`` are ``(date, amount)`` with outflows negative, inflows positive.
    Returns None if it can't bracket/converge (e.g. all flows same sign).
    """
    if len(cashflows) < 2:
        return None
    flows = sorted(cashflows, key=lambda c: c[0])
    t0 = flows[0][0]
    years = [(d - t0).days / 365.0 for d, _ in flows]
    amounts = [a for _, a in flows]
    if not (any(a > 0 for a in amounts) and any(a < 0 for a in amounts)):
        return None

    def npv(rate: float) -> float:
        return sum(a / (1.0 + rate) ** y for a, y in zip(amounts, years))

    from scipy.optimize import brentq

    lo, hi = -0.9999, 10.0
    try:
        if npv(lo) * npv(hi) > 0:
            return None
        return float(brentq(npv, lo, hi, maxiter=200))
    except (ValueError, RuntimeError):
        return None


def money_weighted_return(transactions: Optional[list] = None) -> Optional[float]:
    """IRR-style return (XIRR) accounting for the timing of cash flows.

    Buys are outflows, sells/dividends are inflows, and the current market value
    of remaining holdings is a terminal inflow dated today.
    """
    txns = list_transactions() if transactions is None else transactions
    if not txns:
        return None
    flows: list[tuple[date, float]] = []
    for t in txns:
        gross = t.quantity * t.price
        if t.action == "buy":
            flows.append((t.date, -(gross + t.fees)))
        elif t.action == "sell":
            flows.append((t.date, gross - t.fees))
        elif t.action == "dividend":
            flows.append((t.date, gross))
        # deposit/withdraw/split don't affect investment IRR here.

    # Terminal value of what's still held, valued at the latest cached close.
    terminal = 0.0
    for ticker, qty in current_holdings().items():
        closes = get_closes(ticker)
        if not closes.empty:
            terminal += qty * float(closes.iloc[-1])
    if terminal:
        flows.append((date.today(), terminal))
    return _xirr(flows)


def _aligned(portfolio: pd.Series, benchmark_returns: pd.Series) -> pd.DataFrame:
    return pd.concat([portfolio, benchmark_returns], axis=1).dropna()


def alpha_beta(port_returns: pd.Series, benchmark: str = DEFAULT_BENCHMARK) -> dict:
    """Alpha, beta, tracking error and information ratio vs a benchmark."""
    bench_ticker = BENCHMARKS.get(benchmark, BENCHMARKS[DEFAULT_BENCHMARK])["ticker"]
    bench = get_returns(bench_ticker)
    aligned = _aligned(port_returns, bench)
    if aligned.empty or len(aligned) < 2:
        return {"alpha": None, "beta": None, "tracking_error": None, "information_ratio": None}
    p, b = aligned.iloc[:, 0], aligned.iloc[:, 1]
    excess = p - b
    return {
        "alpha": _f(ep.alpha(p, b, annualization=TRADING_DAYS)),
        "beta": _f(ep.beta(p, b)),
        "tracking_error": _f(excess.std() * np.sqrt(TRADING_DAYS)),
        "information_ratio": _f(ep.excess_sharpe(p, b)),
    }


def per_position_contribution(holdings: Optional[dict] = None, period: str = "ytd") -> list[dict]:
    """Each position's contribution to portfolio return over the period.

    Contribution ≈ start-of-period weight × position period return. Returns a
    list sorted by contribution descending.
    """
    holdings = current_holdings() if holdings is None else holdings
    # Start-of-period market values define the weights.
    weights: dict[str, float] = {}
    period_returns: dict[str, float] = {}
    start_values: dict[str, float] = {}
    for ticker, qty in holdings.items():
        closes = get_closes(ticker)
        if closes.empty:
            continue
        sliced = filter_by_period(closes.pct_change().dropna(), period)
        if sliced.empty:
            continue
        start_px = float(closes[closes.index <= sliced.index.min()].iloc[-1])
        start_values[ticker] = qty * start_px
        period_returns[ticker] = float(ep.cum_returns_final(sliced))
    total_start = sum(start_values.values())
    if not total_start:
        return []
    rows = []
    for ticker in start_values:
        weights[ticker] = start_values[ticker] / total_start
        rows.append({
            "ticker": ticker,
            "weight": round(weights[ticker], 4),
            "position_return": round(period_returns[ticker], 4),
            "contribution": round(weights[ticker] * period_returns[ticker], 4),
        })
    return sorted(rows, key=lambda r: r["contribution"], reverse=True)


def win_rate(port_returns: pd.Series, benchmark: str = DEFAULT_BENCHMARK) -> Optional[float]:
    """Share of months the portfolio's return beat the benchmark's."""
    if port_returns.empty:
        return None
    bench_ticker = BENCHMARKS.get(benchmark, BENCHMARKS[DEFAULT_BENCHMARK])["ticker"]
    bench = get_returns(bench_ticker, freq="M")
    port_m = (1 + port_returns).resample("ME").prod() - 1
    aligned = pd.concat([port_m, bench], axis=1).dropna()
    if aligned.empty:
        return None
    wins = (aligned.iloc[:, 0] > aligned.iloc[:, 1]).sum()
    return float(wins / len(aligned))


def best_worst_periods(port_returns: pd.Series) -> dict:
    """Best / worst single month, quarter and calendar year by total return."""
    if port_returns.empty:
        return {}

    def agg(freq: str) -> tuple[Optional[dict], Optional[dict]]:
        grouped = (1 + port_returns).resample(freq).prod() - 1
        grouped = grouped.dropna()
        if grouped.empty:
            return None, None
        best_i, worst_i = grouped.idxmax(), grouped.idxmin()
        return (
            {"period": pd.Timestamp(best_i).date().isoformat(), "return": round(float(grouped.max()), 4)},
            {"period": pd.Timestamp(worst_i).date().isoformat(), "return": round(float(grouped.min()), 4)},
        )

    m_best, m_worst = agg("ME")
    q_best, q_worst = agg("QE")
    y_best, y_worst = agg("YE")
    return {
        "best_month": m_best, "worst_month": m_worst,
        "best_quarter": q_best, "worst_quarter": q_worst,
        "best_year": y_best, "worst_year": y_worst,
    }


def rolling_metrics(port_returns: pd.Series, window_days: int = TRADING_DAYS,
                    benchmark: str = DEFAULT_BENCHMARK) -> pd.DataFrame:
    """Rolling annualized Sharpe + rolling alpha/beta over ``window_days``.

    Returns a DataFrame indexed by date with columns ``sharpe``, ``alpha``,
    ``beta`` (NaN until the first full window).
    """
    if port_returns.empty:
        return pd.DataFrame(columns=["sharpe", "alpha", "beta"])
    bench_ticker = BENCHMARKS.get(benchmark, BENCHMARKS[DEFAULT_BENCHMARK])["ticker"]
    bench = get_returns(bench_ticker)
    aligned = _aligned(port_returns, bench)
    if len(aligned) < window_days:
        window_days = max(20, len(aligned) // 2)
    p, b = aligned.iloc[:, 0], aligned.iloc[:, 1]

    sharpe = p.rolling(window_days).apply(
        lambda x: ep.sharpe_ratio(x, annualization=TRADING_DAYS), raw=False
    )

    # Rolling alpha/beta via covariance over the window.
    cov = p.rolling(window_days).cov(b)
    var = b.rolling(window_days).var()
    beta = cov / var
    alpha = (p.rolling(window_days).mean() - beta * b.rolling(window_days).mean()) * TRADING_DAYS

    out = pd.DataFrame({"sharpe": sharpe, "alpha": alpha, "beta": beta}).dropna(how="all")
    return out


def _f(value) -> Optional[float]:
    """Coerce a numpy/py scalar to a finite float or None."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def compute_all(period: str = "ytd", benchmark: str = DEFAULT_BENCHMARK) -> dict:
    """Bundle every performance metric for the API (JSON-safe)."""
    returns = portfolio_returns()
    if returns.empty:
        return {"period": period, "benchmark": benchmark, "available": False,
                "reason": "no priced holdings"}
    ab = alpha_beta(returns, benchmark)
    return {
        "period": period,
        "benchmark": benchmark,
        "benchmark_name": BENCHMARKS.get(benchmark, {}).get("name", benchmark),
        "available": True,
        "time_weighted_return": time_weighted_return(returns, period),
        "money_weighted_return": money_weighted_return(),
        "annualized_return": _f(ep.annual_return(filter_by_period(returns, period), annualization=TRADING_DAYS)),
        **ab,
        "win_rate": win_rate(returns, benchmark),
        "best_worst": best_worst_periods(returns),
        "contribution": per_position_contribution(period=period),
    }
