"""Single Stock tab data (Chunk 4): fundamentals, position summary, price series.

Three small, independent lookups the ``/stock-detail/{ticker}`` endpoint bundles:

* :func:`fundamentals` — company header + valuation/quality fields from
  yfinance ``Ticker.info``. Every field is optional: yfinance returns partial
  (or no) data for ETFs, crypto, foreign listings and on rate limits, and the UI
  renders a missing value as "—", so a gap is ``None``, never an exception.
* :func:`position_summary` — cost basis / value / P&L / weight / days held,
  composed from the existing positions + EUR-pricing layers. ``None`` when the
  ticker isn't currently held (the UI then hides the whole card).
* :func:`price_series` — sparkline points off the existing price cache.

``Ticker.info`` is slow and rate-limited, and fundamentals move slowly, so each
ticker's snapshot is cached as ``data/fundamentals_cache/{ticker}.parquet`` for
24h (:data:`core.config.FUNDAMENTALS_TTL_SECONDS`). Failed/empty lookups are
never cached (they'd otherwise pin "—" for a day), and a stale snapshot is
served in preference to nothing when yfinance is unreachable.
"""
from __future__ import annotations

import json
import math
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from core.config import (
    BENCHMARKS,
    DEFAULT_BENCHMARK,
    FUNDAMENTALS_CACHE_DIR,
    FUNDAMENTALS_TTL_SECONDS,
    get_logger,
)
from modules.finance.positions import current_holdings, first_transaction_date, cost_basis, get_position
from modules.finance.price_history import get_closes, get_returns, latest_price_eur, yf_symbol

logger = get_logger(__name__)

# The only ``Ticker.info`` keys we keep — the cache stays small and the module's
# dependence on yfinance's (unstable) field set is explicit in one place.
_INFO_KEYS = (
    "longName", "shortName", "sector", "industry", "exchange", "fullExchangeName",
    "currency", "quoteType", "marketCap", "forwardPE", "trailingPE",
    "revenueGrowth", "operatingMargins", "dividendRate", "trailingAnnualDividendYield",
    "fiftyTwoWeekLow", "fiftyTwoWeekHigh", "freeCashflow", "currentPrice",
    "regularMarketPrice",
)

PERIODS = ("1w", "1m", "3m", "ytd", "1y", "all")
_PERIOD_DAYS = {"1w": 7, "1m": 30, "3m": 91, "1y": 365}
_MAX_POINTS = 600  # downsample long series so "ALL" doesn't ship 2,500 points


# --- yfinance info + 24h parquet cache --------------------------------------

def _cache_file(ticker: str) -> Path:
    safe = ticker.upper().replace("/", "_").replace("^", "_idx_").replace("=", "_eq_")
    return FUNDAMENTALS_CACHE_DIR / f"{safe}.parquet"


def _read_cache(ticker: str) -> tuple[Optional[dict], Optional[float]]:
    """``(info, fetched_at_epoch)`` from the parquet cache, or ``(None, None)``."""
    path = _cache_file(ticker)
    if not path.exists():
        return None, None
    try:
        row = pd.read_parquet(path).iloc[0]
        return json.loads(row["info"]), float(row["fetched_at"])
    except Exception as exc:  # noqa: BLE001 — a corrupt cache file is just a miss
        logger.warning("fundamentals cache unreadable for %s: %s", ticker, exc)
        return None, None


def _write_cache(ticker: str, info: dict) -> None:
    try:
        FUNDAMENTALS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([{"fetched_at": time.time(), "info": json.dumps(info)}]).to_parquet(_cache_file(ticker))
    except Exception as exc:  # noqa: BLE001
        logger.warning("fundamentals cache write failed for %s: %s", ticker, exc)


def _fetch_info(ticker: str) -> dict:
    """Raw yfinance ``Ticker.info`` trimmed to :data:`_INFO_KEYS` ({} on failure)."""
    import yfinance as yf

    try:
        raw = yf.Ticker(yf_symbol(ticker)).info or {}
    except Exception as exc:  # noqa: BLE001 — .info raises on rate limits / unknown symbols
        logger.info("yfinance info failed for %s: %s", ticker, exc)
        return {}
    return {k: raw[k] for k in _INFO_KEYS if raw.get(k) is not None}


def _is_useful(info: dict) -> bool:
    """A snapshot worth caching — has at least a name or a market cap."""
    return bool(info) and any(k in info for k in ("longName", "shortName", "marketCap"))


def get_info(ticker: str) -> dict:
    """Cached-or-fetched ``info`` dict for ``ticker`` (never raises; {} if unknown)."""
    cached, fetched_at = _read_cache(ticker)
    if cached is not None and fetched_at is not None and time.time() - fetched_at < FUNDAMENTALS_TTL_SECONDS:
        return cached
    fresh = _fetch_info(ticker)
    if _is_useful(fresh):
        _write_cache(ticker, fresh)
        return fresh
    return cached or {}  # stale beats nothing


# --- helpers ----------------------------------------------------------------

def _num(v) -> Optional[float]:
    """``v`` as a finite float, else None (yfinance mixes None / 'Infinity' / str)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _ratio(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return a / b if a is not None and b else None


def period_returns(ticker: str) -> dict:
    """``{"ytd": ..., "1y": ...}`` simple price returns from the price cache (None if short)."""
    closes = get_closes(ticker)
    out: dict[str, Optional[float]] = {"ytd": None, "1y": None}
    if closes.empty:
        return out
    last_dt, last = closes.index[-1], float(closes.iloc[-1])
    prior_year = closes[closes.index < pd.Timestamp(year=last_dt.year, month=1, day=1)]
    if not prior_year.empty and float(prior_year.iloc[-1]):
        out["ytd"] = last / float(prior_year.iloc[-1]) - 1
    year_ago = closes[closes.index <= last_dt - pd.Timedelta(days=365)]
    if not year_ago.empty and float(year_ago.iloc[-1]):
        out["1y"] = last / float(year_ago.iloc[-1]) - 1
    return out


# --- public API -------------------------------------------------------------

def fundamentals(ticker: str, benchmark: str = DEFAULT_BENCHMARK) -> dict:
    """Header + fundamentals for ``ticker``; every field ``None`` when unavailable.

    ``ebit_margin`` is yfinance's ``operatingMargins`` (operating income / revenue),
    the closest field it exposes; ``revenue_growth`` is its ``revenueGrowth``
    (most-recent-quarter YoY); ``dividend_yield`` prefers ``dividendRate / price``
    (unambiguous) over yfinance's yield field, whose unit has changed between
    versions. ``beta`` is computed from the cached return series against the
    selected benchmark (not yfinance's fixed-benchmark beta).
    """
    info = get_info(ticker)
    closes = get_closes(ticker)

    price = float(closes.iloc[-1]) if not closes.empty else _num(info.get("currentPrice") or info.get("regularMarketPrice"))
    day_change_pct = None
    if len(closes) >= 2 and float(closes.iloc[-2]):
        day_change_pct = float(closes.iloc[-1]) / float(closes.iloc[-2]) - 1

    market_cap = _num(info.get("marketCap"))
    low, high = _num(info.get("fiftyTwoWeekLow")), _num(info.get("fiftyTwoWeekHigh"))
    range_pos = (price - low) / (high - low) if (price is not None and low is not None and high and high > low) else None

    dividend_rate = _num(info.get("dividendRate"))
    dividend_yield = _ratio(dividend_rate, price) if dividend_rate else _num(info.get("trailingAnnualDividendYield"))

    bench_ticker = BENCHMARKS.get(benchmark, BENCHMARKS[DEFAULT_BENCHMARK])["ticker"]
    beta = None
    if not closes.empty:
        from modules.finance import risk

        beta = risk.beta_vs(get_returns(ticker), bench_ticker)

    return {
        "ticker": ticker.upper(),
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "exchange": info.get("fullExchangeName") or info.get("exchange"),
        "currency": info.get("currency"),
        "quote_type": info.get("quoteType"),
        "price": price,
        "day_change_pct": day_change_pct,
        "as_of": closes.index[-1].date().isoformat() if not closes.empty else None,
        "market_cap": market_cap,
        "pe_forward": _num(info.get("forwardPE")),
        "pe_trailing": _num(info.get("trailingPE")),
        "revenue_growth": _num(info.get("revenueGrowth")),
        "ebit_margin": _num(info.get("operatingMargins")),
        "dividend_yield": dividend_yield,
        "week52_low": low,
        "week52_high": high,
        "week52_position": range_pos,
        "beta": beta,
        "beta_benchmark": benchmark,
        "fcf_yield": _ratio(_num(info.get("freeCashflow")), market_cap),
    }


def position_summary(ticker: str) -> Optional[dict]:
    """Cost basis / value / P&L / weight / days held, or ``None`` if not held.

    EUR-on-EUR like the Holdings endpoint: the ledger's recorded basis is treated
    as EUR and the live price is converted to EUR at the price-fetch boundary.
    Weight comes from :func:`modules.finance.dashboard.holdings_with_day_change`
    so it matches the Portfolio tab exactly. ``days_held`` counts from the first
    transaction in the ticker (not the average lot age).
    """
    from modules.finance.dashboard import holdings_with_day_change

    tu = ticker.upper()
    held = {k.upper(): (k, q) for k, q in current_holdings().items()}
    if tu not in held:
        return None
    key, qty = held[tu]
    avg_cost, total_basis = cost_basis(key)
    lp = latest_price_eur(key)
    value = lp.eur_price * qty if lp else None
    pnl = value - total_basis if value is not None else None
    weight = next((r["weight"] for r in holdings_with_day_change() if r["ticker"].upper() == tu), None)
    first = first_transaction_date(key)
    meta = get_position(key)
    return {
        "ticker": key,
        "name": meta.name if meta else key,
        "quantity": qty,
        "avg_cost": avg_cost,
        "cost_basis": total_basis,
        "current_value": round(value, 2) if value is not None else None,
        "pnl": round(pnl, 2) if pnl is not None else None,
        "pnl_pct": (pnl / total_basis) if (pnl is not None and total_basis) else None,
        "weight": weight,
        "days_held": (date.today() - first).days if first else None,
        "first_bought": first.isoformat() if first else None,
        "fx_stale": bool(lp.fx_stale) if lp else None,
    }


def price_series(ticker: str, period: str = "1y") -> dict:
    """Sparkline points ``[{date, close}]`` for ``period`` off the cached closes."""
    if period not in PERIODS:
        period = "1y"
    closes = get_closes(ticker)
    if closes.empty:
        return {"period": period, "points": [], "change_pct": None}
    if period == "ytd":
        start = pd.Timestamp(year=closes.index[-1].year, month=1, day=1)
        window = closes[closes.index >= start]
    elif period == "all":
        window = closes
    else:
        window = closes[closes.index >= closes.index[-1] - timedelta(days=_PERIOD_DAYS[period])]
    if len(window) > _MAX_POINTS:
        step = math.ceil(len(window) / _MAX_POINTS)
        window = pd.concat([window.iloc[::step], window.iloc[[-1]]]).loc[lambda s: ~s.index.duplicated()]
    change = None
    if len(window) >= 2 and float(window.iloc[0]):
        change = float(window.iloc[-1]) / float(window.iloc[0]) - 1
    return {
        "period": period,
        "points": [{"date": d.date().isoformat(), "close": round(float(v), 4)} for d, v in window.items()],
        "change_pct": change,
    }


def stock_detail(ticker: str, period: str = "1y", benchmark: str = DEFAULT_BENCHMARK) -> dict:
    """Everything the Single Stock tab needs for one ticker, in one round trip."""
    return {
        "ticker": ticker.upper(),
        "fundamentals": fundamentals(ticker, benchmark),
        "position": position_summary(ticker),
        "series": price_series(ticker, period),
    }
