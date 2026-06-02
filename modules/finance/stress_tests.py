"""Historical-shock stress tests (Phase 15e, Category G S-priority).

"How would *today's* portfolio have done if a past crisis happened again?" For
each named shock window we take the current holdings, look up each ticker's
actual cumulative return over that window, and apply it to the current market
value. Holdings that didn't exist yet in the window (e.g. a coin pre-2008) are
estimated from their beta to the benchmark times the benchmark's window return,
so nothing is silently dropped — each estimated position is flagged.
"""
from __future__ import annotations

from datetime import date, datetime

import empyrical as ep

from core.config import BENCHMARKS, DEFAULT_BENCHMARK, get_logger
from modules.finance import risk
from modules.finance.positions import current_holdings, get_position
from modules.finance.price_history import get_closes, get_returns

logger = get_logger(__name__)

# Canonical crisis windows (peak-ish → trough-ish).
HISTORICAL_SHOCKS: dict[str, dict] = {
    "2008_GFC": {"label": "2008 Global Financial Crisis", "start": "2008-09-01", "end": "2009-03-31"},
    "2020_COVID": {"label": "2020 COVID crash", "start": "2020-02-19", "end": "2020-03-23"},
    "2022_RATES": {"label": "2022 rate-hike drawdown", "start": "2022-01-01", "end": "2022-10-12"},
}


def _window_return(ticker: str, start: date, end: date) -> float | None:
    """Cumulative simple return of a ticker between two dates (None if no data)."""
    closes = get_closes(ticker)
    if closes.empty:
        return None
    window = closes[(closes.index.date >= start) & (closes.index.date <= end)]
    if len(window) < 2:
        return None
    return float(window.iloc[-1] / window.iloc[0] - 1.0)


def replay_historical_period(period_key: str, holdings: dict | None = None) -> dict:
    """Simulate current holdings through a historical shock window.

    ``holdings`` defaults to the live transaction-derived holdings. Returns total
    P&L, per-position impact, and the benchmark's move over the same window.
    """
    if period_key not in HISTORICAL_SHOCKS:
        return {"available": False, "reason": f"unknown shock '{period_key}'",
                "known": list(HISTORICAL_SHOCKS)}
    shock = HISTORICAL_SHOCKS[period_key]
    start = datetime.strptime(shock["start"], "%Y-%m-%d").date()
    end = datetime.strptime(shock["end"], "%Y-%m-%d").date()

    holdings = current_holdings() if holdings is None else holdings
    if not holdings:
        return {"available": False, "reason": "no holdings"}

    bench_ticker = BENCHMARKS[DEFAULT_BENCHMARK]["ticker"]
    bench_ret = _window_return(bench_ticker, start, end)

    per_position: dict[str, dict] = {}
    total_value = 0.0
    total_impact = 0.0
    for ticker, qty in holdings.items():
        closes = get_closes(ticker)
        price = float(closes.iloc[-1]) if not closes.empty else None
        if price is None:
            per_position[ticker] = {"error": "no current price"}
            continue
        value = qty * price
        total_value += value

        shock_ret = _window_return(ticker, start, end)
        estimated = False
        if shock_ret is None:
            # No history in the window — estimate via beta × benchmark move.
            beta = risk.beta_vs(get_returns(ticker), bench_ticker)
            if beta is None or bench_ret is None:
                per_position[ticker] = {"value": round(value, 2),
                                        "error": "no window history and no beta estimate"}
                continue
            shock_ret = beta * bench_ret
            estimated = True

        impact = value * shock_ret
        total_impact += impact
        per_position[ticker] = {
            "value": round(value, 2),
            "shock_return": round(shock_ret, 4),
            "impact": round(impact, 2),
            "estimated": estimated,
        }

    return {
        "available": True,
        "shock": period_key,
        "label": shock["label"],
        "start": shock["start"],
        "end": shock["end"],
        "benchmark": DEFAULT_BENCHMARK,
        "benchmark_return": round(bench_ret, 4) if bench_ret is not None else None,
        "total_value": round(total_value, 2),
        "total_estimated_impact": round(total_impact, 2),
        "impact_pct": round(total_impact / total_value, 4) if total_value else None,
        "per_position": per_position,
    }


def replay_all() -> dict:
    """Run every known shock against the current portfolio (for the UI table)."""
    return {key: replay_historical_period(key) for key in HISTORICAL_SHOCKS}
