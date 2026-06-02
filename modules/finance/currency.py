"""Currency conversion + multi-currency reporting (Phase 15e, Category K).

Everything in the 15a–15d layer was computed in each price series' native
currency (mostly USD on yfinance), weighted by market value. This module adds a
reporting-currency layer on top: FX rates (via yfinance ``EURUSD=X``-style
pairs, cached through the same parquet store as equities), a currency breakdown
of the portfolio, and a hedged-vs-unhedged decomposition that isolates how much
of the portfolio's return came from the assets vs. the currency drift.

David reports in EUR by default; USD is the only other reporting currency.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from core.config import get_logger
from modules.finance.price_history import backfill_history, get_closes

logger = get_logger(__name__)

REPORTING_CURRENCIES = ["EUR", "USD"]
DEFAULT_REPORTING = "EUR"


def _fx_pair(from_ccy: str, to_ccy: str) -> str:
    """yfinance FX symbol for a currency pair (e.g. ``EURUSD=X``)."""
    return f"{from_ccy.upper()}{to_ccy.upper()}=X"


def fx_series(from_ccy: str, to_ccy: str) -> pd.Series:
    """Daily close series of ``from→to`` FX rate (empty Series if unavailable).

    Uses the parquet-cached backfill so repeated conversions don't re-hit the
    network. ``from == to`` returns an empty series (callers treat that as 1.0).
    """
    if from_ccy.upper() == to_ccy.upper():
        return pd.Series(dtype="float64")
    return get_closes(_fx_pair(from_ccy, to_ccy))


def get_fx_rate(from_ccy: str, to_ccy: str, on_date: Optional[date] = None) -> Optional[float]:
    """FX rate for ``from→to`` on (or just before) ``on_date`` (today by default).

    Returns ``None`` if no rate is available so callers can flag the gap rather
    than silently converting at a wrong rate.
    """
    if from_ccy.upper() == to_ccy.upper():
        return 1.0
    closes = fx_series(from_ccy, to_ccy)
    if closes.empty:
        # Fall back to the inverse pair if the direct one has no data.
        inv = fx_series(to_ccy, from_ccy)
        if inv.empty:
            logger.warning("No FX data for %s%s", from_ccy, to_ccy)
            return None
        closes = 1.0 / inv
    on_date = on_date or date.today()
    valid = closes[closes.index.date <= on_date]
    return float(valid.iloc[-1]) if not valid.empty else None


def convert(amount: float, from_ccy: str, to_ccy: str, on_date: Optional[date] = None) -> Optional[float]:
    """Convert ``amount`` from one currency to another (None if no rate)."""
    rate = get_fx_rate(from_ccy, to_ccy, on_date)
    if rate is None:
        return None
    return amount * rate


def position_currency_breakdown(positions: list, prices: dict, to_ccy: str = DEFAULT_REPORTING) -> dict:
    """How much of the portfolio sits in each native currency.

    ``positions`` are ``{ticker, quantity, currency}`` dicts; ``prices`` maps
    ticker → latest price *in that position's native currency*. Values are
    converted to ``to_ccy`` for a comparable total. Returns per-currency value +
    weight, plus a ``fx_missing`` list for currencies we couldn't price.
    """
    by_ccy: dict[str, float] = {}
    fx_missing: list[str] = []
    for p in positions:
        ccy = (p.get("currency") or "USD").upper()
        native_value = p.get("quantity", 0) * prices.get(p["ticker"], 0)
        converted = convert(native_value, ccy, to_ccy)
        if converted is None:
            fx_missing.append(ccy)
            converted = native_value  # fall back to native amount, flagged below
        by_ccy[ccy] = by_ccy.get(ccy, 0.0) + converted
    total = sum(by_ccy.values())
    return {
        "reporting_currency": to_ccy.upper(),
        "total_value": total,
        "by_currency": {
            ccy: {"value": v, "weight": (v / total if total else 0.0)}
            for ccy, v in sorted(by_ccy.items(), key=lambda kv: kv[1], reverse=True)
        },
        "fx_missing": sorted(set(fx_missing)),
    }


def reporting_value_series(to_ccy: str = DEFAULT_REPORTING) -> pd.Series:
    """Daily portfolio market-value series expressed in ``to_ccy``.

    Each held ticker's native close × quantity is converted day-by-day using the
    native→reporting FX series (forward-filled), then summed. Tickers with no
    price data are skipped; a holding whose currency has no FX series is kept in
    native terms (better than dropping it). Empty Series if nothing resolves.
    """
    from modules.finance.positions import current_holdings, get_position

    holdings = current_holdings()
    cols: dict[str, pd.Series] = {}
    for ticker, qty in holdings.items():
        closes = get_closes(ticker)
        if closes.empty:
            continue
        native_value = closes * qty
        meta = get_position(ticker)
        ccy = (meta.currency if meta else "USD").upper()
        if ccy != to_ccy.upper():
            fx = fx_series(ccy, to_ccy)
            if not fx.empty:
                fx = fx.reindex(native_value.index).ffill().bfill()
                native_value = native_value * fx
        cols[ticker] = native_value
    if not cols:
        return pd.Series(dtype="float64")
    frame = pd.DataFrame(cols).sort_index().ffill().dropna(how="all")
    return frame.sum(axis=1, min_count=1).dropna()


def reporting_returns(to_ccy: str = DEFAULT_REPORTING) -> pd.Series:
    """Daily simple returns of the reporting-currency portfolio value series."""
    values = reporting_value_series(to_ccy)
    if values.empty:
        return pd.Series(dtype="float64")
    return values.pct_change().dropna()


def hedged_vs_unhedged(
    positions: list,
    base_returns: pd.Series,
    to_ccy: str = DEFAULT_REPORTING,
) -> dict:
    """Decompose reporting-currency return into asset return + currency drift.

    ``base_returns`` is the portfolio's daily return series in the assets' native
    terms (the existing 15a series). For each native currency present we build a
    value-weighted FX return series (native→``to_ccy``); the *unhedged* return is
    the asset return plus that currency drift, while the *hedged* return strips
    the drift out. The gap is the currency contribution.
    """
    if base_returns is None or base_returns.empty:
        return {"available": False, "reason": "no base return series"}

    # Currency weights from the supplied positions (native value share).
    weights: dict[str, float] = {}
    for p in positions:
        ccy = (p.get("currency") or "USD").upper()
        weights[ccy] = weights.get(ccy, 0.0) + p.get("_value", 0.0)
    total = sum(weights.values())
    if total <= 0:
        return {"available": False, "reason": "no positioned value"}
    weights = {c: v / total for c, v in weights.items()}

    # Weighted FX drift: for each foreign currency, its native→reporting daily
    # return, weighted by that currency's portfolio share.
    fx_drift = pd.Series(0.0, index=base_returns.index)
    contributed = False
    for ccy, w in weights.items():
        if ccy == to_ccy.upper():
            continue
        closes = fx_series(ccy, to_ccy)
        if closes.empty:
            continue
        fx_ret = closes.pct_change().reindex(base_returns.index).fillna(0.0)
        fx_drift = fx_drift + w * fx_ret
        contributed = True

    if not contributed:
        return {
            "available": True,
            "reporting_currency": to_ccy.upper(),
            "hedged_return": float((1 + base_returns).prod() - 1),
            "unhedged_return": float((1 + base_returns).prod() - 1),
            "currency_contribution": 0.0,
            "note": "portfolio is entirely in the reporting currency",
        }

    hedged = (1 + base_returns).prod() - 1
    unhedged = (1 + (base_returns + fx_drift)).prod() - 1
    return {
        "available": True,
        "reporting_currency": to_ccy.upper(),
        "hedged_return": float(hedged),
        "unhedged_return": float(unhedged),
        "currency_contribution": float(unhedged - hedged),
    }
