"""Benchmark comparison (Chunk 5): MSCI World vs S&P 500 vs DAX 40 vs STOXX 600.

Everything here is computed off one **aligned window** so the numbers are
directly comparable:

1. Daily closes for each benchmark (tickers from ``core.config.BENCHMARKS`` —
   the very ones the Risk tab dropdown resolves; no new ticker variants).
2. Inner-joined on the dates *all available* benchmarks traded. Exchanges keep
   different holiday calendars, and a return computed between two aligned
   closes spans the same calendar interval for every benchmark. (The cost: a
   day one market was shut is dropped for all, so vol reads marginally low —
   a ~1% effect that is the same for every row.)
3. Sliced to the period with :func:`performance.filter_by_period`.

Return / volatility / Sharpe / correlation then come straight from the aligned
window, with vol and Sharpe delegated to :mod:`risk` (Sharpe uses the same
``DEFAULT_RISK_FREE_RATE`` as the Optimization tab). A benchmark whose price
cache is empty is reported as unavailable (all-``None`` metrics, no series, no
matrix row) rather than failing the whole comparison.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from core.config import BENCHMARKS, DEFAULT_RISK_FREE_RATE, get_logger
from modules.finance import risk
from modules.finance.performance import filter_by_period
from modules.finance.price_history import get_closes

logger = get_logger(__name__)

# Display order: MSCI World is the primary reference (correlation column is
# "to MSCI World"), then the rest. BENCHMARKS' own dict order is not the UI order.
ORDER = ["MSCI_WORLD", "SPY", "DAX", "STOXX_600"]
PRIMARY = "MSCI_WORLD"
PERIODS = ("1m", "3m", "6m", "ytd", "1y", "3y", "all")
DEFAULT_PERIOD = "1y"

_EMPTY_METRICS = {"return": None, "vol": None, "sharpe": None, "correlation_to_msci": None}


def normalize_period(period: Optional[str]) -> str:
    """Lower-case a period ("1Y" -> "1y"); unknown values fall back to the default."""
    p = (period or DEFAULT_PERIOD).lower()
    return p if p in PERIODS else DEFAULT_PERIOD


def _aligned_window(period: str) -> pd.DataFrame:
    """Aligned closes (columns = available benchmark keys) sliced to ``period``.

    The first row is the period's base (indexed series start at 100 there); an
    empty frame means no benchmark had data.
    """
    cols: dict[str, pd.Series] = {}
    for key in ORDER:
        closes = get_closes(BENCHMARKS[key]["ticker"])
        if closes.empty:
            logger.warning("No price data for benchmark %s (%s)", key, BENCHMARKS[key]["ticker"])
            continue
        cols[key] = closes
    if not cols:
        return pd.DataFrame()
    frame = pd.DataFrame(cols).dropna()
    return filter_by_period(frame, period) if not frame.empty else frame


def _available(frame: pd.DataFrame) -> list[str]:
    return [k for k in ORDER if k in frame.columns]


def _metrics(frame: pd.DataFrame, risk_free: float = DEFAULT_RISK_FREE_RATE) -> dict[str, dict]:
    out: dict[str, dict] = {k: dict(_EMPTY_METRICS) for k in ORDER}
    if len(frame) < 2:
        return out
    rets = frame.pct_change().dropna()
    corr = rets.corr() if len(rets) >= 2 else None
    for key in _available(frame):
        r = rets[key]
        out[key] = {
            "return": float(frame[key].iloc[-1] / frame[key].iloc[0] - 1),
            "vol": risk.annualized_vol(r),
            "sharpe": risk.sharpe(r, risk_free),
            "correlation_to_msci": (
                risk._f(corr.loc[key, PRIMARY]) if corr is not None and PRIMARY in corr.columns else None
            ),
        }
    return out


def _matrix(frame: pd.DataFrame) -> dict:
    keys = _available(frame)
    if len(frame) < 3 or not keys:
        return {"keys": keys, "labels": [BENCHMARKS[k]["name"] for k in keys], "matrix": []}
    corr = frame.pct_change().dropna()[keys].corr()
    return {
        "keys": keys,
        "labels": [BENCHMARKS[k]["name"] for k in keys],
        "matrix": [[risk._f(corr.loc[a, b]) for b in keys] for a in keys],
    }


def _series(frame: pd.DataFrame) -> list[dict]:
    if frame.empty:
        return []
    indexed = frame / frame.iloc[0] * 100.0
    keys = _available(indexed)
    return [
        {"date": d.date().isoformat(), **{k: round(float(row[k]), 4) for k in keys}}
        for d, row in indexed.iterrows()
    ]


def benchmark_metrics(period: str = DEFAULT_PERIOD, risk_free: float = DEFAULT_RISK_FREE_RATE) -> dict[str, dict]:
    """``{key: {return, vol, sharpe, correlation_to_msci}}`` for every benchmark.

    ``return`` is the simple total return over the window, ``vol`` the annualized
    volatility of daily returns, ``sharpe`` uses the shared risk-free rate.
    ``correlation_to_msci`` is 1.0 for MSCI World itself (the UI shows it as
    "—"); unavailable benchmarks get all-``None``.
    """
    return _metrics(_aligned_window(normalize_period(period)), risk_free)


def benchmark_correlation_matrix(period: str = DEFAULT_PERIOD) -> dict:
    """Full N×N correlation matrix of daily returns over ``period``.

    ``{"keys": [...], "labels": [...], "matrix": [[...]]}`` over the *available*
    benchmarks in display order. Symmetric with a unit diagonal by construction.
    """
    return _matrix(_aligned_window(normalize_period(period)))


def benchmark_indexed_series(period: str = DEFAULT_PERIOD) -> list[dict]:
    """Chart rows ``[{"date": ..., "MSCI_WORLD": 100.0, "SPY": ..., ...}]``, each
    benchmark indexed to 100 at the first date of the window."""
    return _series(_aligned_window(normalize_period(period)))


def compare(period: str = DEFAULT_PERIOD, risk_free: float = DEFAULT_RISK_FREE_RATE) -> dict:
    """Everything the Benchmarks tab renders, in one call (metrics + matrix +
    series), off a single aligned window so all three views agree."""
    period = normalize_period(period)
    frame = _aligned_window(period)
    return {
        "period": period,
        "start": frame.index[0].date().isoformat() if not frame.empty else None,
        "end": frame.index[-1].date().isoformat() if not frame.empty else None,
        "risk_free_rate": risk_free,
        "benchmarks": [
            {"key": k, "name": BENCHMARKS[k]["name"], "ticker": BENCHMARKS[k]["ticker"],
             "available": k in frame.columns}
            for k in ORDER
        ],
        "metrics": _metrics(frame, risk_free),
        "correlation": _matrix(frame),
        "series": _series(frame),
    }
