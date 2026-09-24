"""Portfolio Hub "Portfolio" tab aggregates (Chunk 2).

Backs the new tab's KPI band, indexed performance chart and top-holdings list.
Deliberately thin: every figure here composes an existing pure function from
positions / price_history / performance / risk / buckets / period_pnl rather
than recomputing metrics those modules already own — the one new computation
is per-holding day-over-day change, which nothing else in the app needed yet.

Day-change caveat: like the rest of the 15a performance layer (see
performance.py's module docstring), the day-change *percentage* is derived
from each ticker's own native-currency close series — a same-day FX move is
assumed negligible, the same simplification portfolio_returns() already makes
for every longer window. The EUR *amount* is anchored to the real EUR-converted
current value (latest_price_eur), so the headline euro figures stay correct;
only the 1-day rate is a native-currency approximation.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from core.config import BENCHMARKS, DEFAULT_BENCHMARK, get_logger
from modules.finance import risk as risk_mod
from modules.finance.buckets import bucket_allocation, resolve_bucket_with_source
from modules.finance.performance import filter_by_period, portfolio_returns, time_weighted_return
from modules.finance.period_pnl import position_period_pnl
from modules.finance.positions import current_holdings, get_position
from modules.finance.price_history import get_closes, get_returns, latest_price_eur

logger = get_logger(__name__)


def _bench_ticker(benchmark: str) -> str:
    return BENCHMARKS.get(benchmark, BENCHMARKS[DEFAULT_BENCHMARK])["ticker"]


def holdings_with_day_change() -> list[dict]:
    """Every current holding valued in EUR, with portfolio weight + 1-day change."""
    rows: list[dict] = []
    for ticker, qty in current_holdings().items():
        lp = latest_price_eur(ticker)
        if lp is None:
            continue
        value_eur = lp.eur_price * qty
        closes = get_closes(ticker)
        day_pct: Optional[float] = None
        if len(closes) >= 2:
            prev, last = float(closes.iloc[-2]), float(closes.iloc[-1])
            if prev:
                day_pct = (last - prev) / prev
        meta = get_position(ticker)
        bucket, bucket_source = resolve_bucket_with_source(ticker)
        rows.append({
            "ticker": ticker,
            "name": meta.name if meta else ticker,
            "bucket": bucket,
            "bucket_source": bucket_source,
            "value_eur": round(value_eur, 2),
            "day_change_pct": round(day_pct, 6) if day_pct is not None else None,
            "day_change_eur": round(value_eur * day_pct, 2) if day_pct is not None else None,
        })

    total = sum(r["value_eur"] for r in rows)
    for r in rows:
        r["weight"] = round(r["value_eur"] / total, 4) if total > 0 else None
    rows.sort(key=lambda r: r["value_eur"], reverse=True)
    return rows


def _worst_drift_bucket() -> Optional[dict]:
    """The bucket with the largest |drift| from bucket_allocation(), if any holdings exist."""
    buckets = bucket_allocation().get("buckets", [])
    worst: Optional[dict] = None
    for b in buckets:
        if worst is None or abs(b["drift"]) > abs(worst["drift"]):
            worst = b
    return worst


def summary(benchmark: str = DEFAULT_BENCHMARK) -> dict:
    """KPI-band + top-holdings bundle for the Portfolio tab's first paint."""
    rows = holdings_with_day_change()
    total_value = round(sum(r["value_eur"] for r in rows), 2)
    day_deltas = [r["day_change_eur"] for r in rows if r["day_change_eur"] is not None]
    day_change_eur = round(sum(day_deltas), 2) if day_deltas else None
    prior_value = (total_value - day_change_eur) if day_change_eur is not None else None
    day_change_pct = (
        round(day_change_eur / prior_value, 6) if prior_value else None
    )

    bench_ticker = _bench_ticker(benchmark)
    port_returns = portfolio_returns()
    bench_returns = get_returns(bench_ticker)

    ytd_pct = time_weighted_return(port_returns, "ytd") if not port_returns.empty else None
    bench_ytd_pct = time_weighted_return(bench_returns, "ytd") if not bench_returns.empty else None

    pnl = position_period_pnl() if rows else {}
    ytd_eur = pnl.get("pnl_ytd_total") if pnl.get("count") else None

    sharpe_1y = risk_mod.sharpe(filter_by_period(port_returns, "1y")) if not port_returns.empty else None
    bench_sharpe_1y = risk_mod.sharpe(filter_by_period(bench_returns, "1y")) if not bench_returns.empty else None

    return {
        "available": len(rows) > 0,
        "benchmark": benchmark,
        "benchmark_name": BENCHMARKS.get(benchmark, {}).get("name", benchmark),
        "portfolio_value_eur": total_value,
        "day_change_eur": day_change_eur,
        "day_change_pct": day_change_pct,
        "ytd_return_pct": ytd_pct,
        "ytd_return_eur": ytd_eur,
        "benchmark_ytd_return_pct": bench_ytd_pct,
        "sharpe_1y": sharpe_1y,
        "benchmark_sharpe_1y": bench_sharpe_1y,
        "worst_drift_bucket": _worst_drift_bucket(),
        "top_holdings": rows[:5],
        "holdings_count": len(rows),
    }


# Periods this endpoint accepts, in addition to performance.filter_by_period's
# own ytd/1y/3y/5y/all (1d/1w/1m registered there for this tab's toggle).
INDEXED_PERIODS = ("1d", "1w", "1m", "ytd", "1y", "all")


def indexed_performance(period: str = "1w", benchmark: str = DEFAULT_BENCHMARK) -> dict:
    """Portfolio + benchmark value, both indexed to 100 at the start of ``period``.

    ``1d`` is honest about the data's real granularity: the price cache is daily
    closes only (no intraday), so a "1D" window can only ever have one or two
    points — this degrades to ``available: False`` with a clear reason rather
    than rendering a near-empty line.
    """
    port_returns = portfolio_returns()
    bench_ticker = _bench_ticker(benchmark)
    bench_returns = get_returns(bench_ticker)

    if port_returns.empty or bench_returns.empty:
        return {
            "available": False,
            "reason": "no priced holdings",
            "period": period,
            "benchmark": benchmark,
            "series": [],
        }

    p = filter_by_period(port_returns, period)
    b = filter_by_period(bench_returns, period)
    aligned = pd.concat([p, b], axis=1).dropna()
    aligned.columns = ["portfolio", "benchmark"]

    if len(aligned) < 2:
        reason = (
            "only daily close data available — 1D has no intraday points"
            if period == "1d"
            else "not enough overlapping price history for this window"
        )
        return {
            "available": False,
            "reason": reason,
            "period": period,
            "benchmark": benchmark,
            "series": [],
        }

    idx = (1 + aligned).cumprod()
    idx = idx / idx.iloc[0] * 100  # re-base so the first row is exactly 100

    series = [
        {
            "date": pd.Timestamp(i).date().isoformat(),
            "portfolio": round(float(row["portfolio"]), 2),
            "benchmark": round(float(row["benchmark"]), 2),
        }
        for i, row in idx.iterrows()
    ]
    return {
        "available": True,
        "period": period,
        "benchmark": benchmark,
        "benchmark_name": BENCHMARKS.get(benchmark, {}).get("name", benchmark),
        "series": series,
    }
