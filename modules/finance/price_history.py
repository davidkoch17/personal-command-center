"""Daily price backfill + parquet cache for held / watchlist / benchmark tickers.

Wraps yfinance with an on-disk parquet cache so repeated metric computations
don't re-hit the network. One file per ticker under ``data/price_cache/``.

yfinance (>=0.2) returns a *MultiIndex*-columned frame even for a single ticker
(level 0 = OHLCV field, level 1 = ticker); we flatten that to plain OHLCV here so
downstream code can just do ``df["Close"]``.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Optional

import pandas as pd

from core.config import PRICE_CACHE_DIR, get_logger

logger = get_logger(__name__)

Freq = Literal["D", "W", "M"]

# Canonical (held) ticker -> yfinance download symbol. Crypto needs a quote
# suffix; equities/ETFs pass through unchanged.
_YF_SYMBOL_OVERRIDES = {
    "SOL": "SOL-USD",
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
}


def yf_symbol(ticker: str) -> str:
    """Resolve a stored ticker to the symbol yfinance expects."""
    return _YF_SYMBOL_OVERRIDES.get(ticker.upper(), ticker)


def _flatten(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Collapse yfinance's MultiIndex columns to plain OHLCV (single level)."""
    if isinstance(df.columns, pd.MultiIndex):
        # Drop the ticker level; keep the OHLCV field names.
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def _cache_file(ticker: str):
    return PRICE_CACHE_DIR / f"{ticker.replace('/', '_').replace('^', '_idx_')}.parquet"


def backfill_history(ticker: str, start_date: Optional[date] = None) -> pd.DataFrame:
    """Download daily history from yfinance and cache it as parquet.

    ``start_date`` defaults to 10 years back. Returns a DataFrame indexed by date
    with OHLCV columns (possibly empty if the symbol has no data). A fresh-enough
    cache (updated today) is served as-is; otherwise the tail is topped up.
    """
    import yfinance as yf

    PRICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_file(ticker)
    symbol = yf_symbol(ticker)
    if start_date is None:
        start_date = date.today() - timedelta(days=365 * 10)

    if cache_file.exists():
        try:
            df = pd.read_parquet(cache_file)
        except Exception as exc:  # noqa: BLE001 — corrupt cache -> re-download
            logger.warning("Bad price cache for %s (%s); refetching", ticker, exc)
            df = pd.DataFrame()
        if not df.empty:
            last_date = pd.Timestamp(df.index.max()).date()
            if (date.today() - last_date).days < 1:
                return df
            new = yf.download(
                symbol,
                start=last_date + timedelta(days=1),
                end=date.today() + timedelta(days=1),
                progress=False,
                auto_adjust=True,
            )
            new = _flatten(new, symbol)
            if not new.empty:
                df = pd.concat([df, new])
                df = df[~df.index.duplicated(keep="last")].sort_index()
                df.to_parquet(cache_file)
            return df

    df = yf.download(
        symbol,
        start=start_date,
        end=date.today() + timedelta(days=1),
        progress=False,
        auto_adjust=True,
    )
    df = _flatten(df, symbol)
    if not df.empty:
        df = df.sort_index()
        df.to_parquet(cache_file)
    else:
        logger.warning("No price history returned for %s (%s)", ticker, symbol)
    return df


def get_closes(ticker: str) -> pd.Series:
    """Clean adjusted-close series for a ticker (empty Series if unavailable)."""
    df = backfill_history(ticker)
    if df.empty or "Close" not in df.columns:
        return pd.Series(dtype="float64")
    closes = df["Close"].dropna()
    closes.index = pd.to_datetime(closes.index)
    return closes


def get_returns(ticker: str, freq: Freq = "D") -> pd.Series:
    """Periodic simple returns for a ticker at daily / weekly / monthly frequency."""
    closes = get_closes(ticker)
    if closes.empty:
        return pd.Series(dtype="float64")
    if freq == "W":
        closes = closes.resample("W").last()
    elif freq == "M":
        closes = closes.resample("ME").last()  # "ME" = month-end (pandas 2.2+)
    return closes.pct_change().dropna()


def get_price_on(ticker: str, target_date: date) -> Optional[float]:
    """Closest available close on or before ``target_date`` (None if none)."""
    closes = get_closes(ticker)
    if closes.empty:
        return None
    valid = closes[closes.index.date <= target_date]
    return float(valid.iloc[-1]) if not valid.empty else None


def latest_price(ticker: str) -> Optional[float]:
    """Most recent available close for a ticker (None if no data).

    Value is in the instrument's *native* quote currency (USD for US-listed
    names and crypto-USD pairs). For EUR-denominated reporting use
    :func:`latest_price_eur`, which converts before returning.
    """
    closes = get_closes(ticker)
    return float(closes.iloc[-1]) if not closes.empty else None


# --- EUR conversion layer (Phase 15a P&L fix) -------------------------------
#
# yfinance quotes US-listed equities/ADRs and crypto-USD pairs in USD, but the
# transaction log records cost basis in EUR — so unrealized P&L computed from a
# raw ``latest_price`` mixed currencies. This layer fetches the quote currency
# from yfinance, converts the live price to EUR at the price-fetch boundary, and
# exposes the conversion as metadata so downstream P&L is EUR-on-EUR.

REPORTING_CURRENCY = "EUR"
_FX_TTL_SECONDS = 3600.0  # 1h: live FX rarely moves enough to matter intraday

# In-memory caches (per process). Quote currency is effectively static, so it is
# cached without expiry; FX rates carry a 1h TTL and a last-good fallback.
_quote_ccy_cache: dict[str, str] = {}
_fx_cache: dict[str, tuple[float, float]] = {}  # ccy -> (native->EUR rate, epoch)


@dataclass
class LivePrice:
    """A live price converted to EUR, with the conversion kept as metadata.

    ``eur_price`` is the canonical value for valuation/P&L. ``native_price`` /
    ``native_currency`` / ``fx_rate`` (native→EUR) are retained for logging and
    debugging. ``fx_stale`` flags that conversion used a fallback cached rate (or
    couldn't convert at all), so callers can surface a "stale FX" warning.
    """

    ticker: str
    native_price: float
    native_currency: str
    fx_rate: float
    eur_price: float
    fx_stale: bool = False


def quote_currency(ticker: str) -> str:
    """Quote currency for ``ticker`` per yfinance ``fast_info`` (cached).

    Falls back to ``USD`` when the lookup fails or returns nothing — both the
    US-listed equities/ADRs and the ``*-USD`` crypto pairs we hold quote in USD,
    so that is the safe default.
    """
    tu = ticker.upper()
    if tu in _quote_ccy_cache:
        return _quote_ccy_cache[tu]
    symbol = yf_symbol(ticker)
    ccy: Optional[str] = None
    try:
        import yfinance as yf

        fast = yf.Ticker(symbol).fast_info
        try:
            ccy = fast["currency"]  # FastInfo supports mapping access
        except (KeyError, TypeError):
            ccy = getattr(fast, "currency", None)
    except Exception as exc:  # noqa: BLE001 — degrade to default rather than crash
        logger.warning("Quote-currency lookup failed for %s (%s): %s", ticker, symbol, exc)
    ccy = (ccy or "USD").upper()
    _quote_ccy_cache[tu] = ccy
    return ccy


def _fetch_fx_to_eur(from_ccy: str) -> Optional[float]:
    """Latest ``from_ccy``→EUR rate via yfinance FX pairs (None if unavailable).

    Tries the direct ``<ccy>EUR=X`` pair first (e.g. ``USDEUR=X``), then the
    inverse ``EUR<ccy>=X`` (e.g. ``EURUSD=X``) and reciprocates it. Both go
    through the parquet-cached :func:`get_closes`, so this rarely hits network.
    """
    fc = from_ccy.upper()
    if fc == REPORTING_CURRENCY:
        return 1.0
    closes = get_closes(f"{fc}{REPORTING_CURRENCY}=X")
    if not closes.empty:
        return float(closes.iloc[-1])
    inv = get_closes(f"{REPORTING_CURRENCY}{fc}=X")
    if not inv.empty:
        last = float(inv.iloc[-1])
        if last:
            return 1.0 / last
    return None


def fx_rate_to_eur(from_ccy: str) -> tuple[Optional[float], bool]:
    """``(rate, stale)`` for ``from_ccy``→EUR, with a 1h cache + last-good fallback.

    A fresh rate (<1h old) is served from cache. Otherwise a refetch is
    attempted; on failure the last cached rate is returned flagged ``stale=True``,
    and only if nothing was ever cached do we return ``(None, True)``.
    """
    fc = from_ccy.upper()
    if fc == REPORTING_CURRENCY:
        return 1.0, False
    now = time.time()
    cached = _fx_cache.get(fc)
    if cached is not None and (now - cached[1]) < _FX_TTL_SECONDS:
        return cached[0], False
    rate = _fetch_fx_to_eur(fc)
    if rate is not None:
        _fx_cache[fc] = (rate, now)
        return rate, False
    if cached is not None:
        logger.warning("FX %s->EUR refetch failed; using stale cached rate %.4f", fc, cached[0])
        return cached[0], True
    logger.warning("FX %s->EUR unavailable and no cached rate to fall back on", fc)
    return None, True


def latest_price_eur(ticker: str, native_currency: Optional[str] = None) -> Optional[LivePrice]:
    """Latest price for ``ticker`` converted to EUR (None if no price at all).

    ``native_currency`` may be supplied to skip the yfinance currency lookup;
    otherwise it is resolved via :func:`quote_currency`. If FX is unavailable the
    native price is returned unconverted with ``fx_stale=True`` so the caller can
    flag it rather than silently report a wrong-currency number.
    """
    native = latest_price(ticker)
    if native is None:
        return None
    ccy = (native_currency or quote_currency(ticker)).upper()
    if ccy == REPORTING_CURRENCY:
        return LivePrice(ticker, native, REPORTING_CURRENCY, 1.0, native, False)
    rate, stale = fx_rate_to_eur(ccy)
    if rate is None:
        logger.warning("No %s->EUR rate for %s; returning native price unconverted", ccy, ticker)
        return LivePrice(ticker, native, ccy, 1.0, native, True)
    return LivePrice(ticker, native, ccy, rate, native * rate, stale)
