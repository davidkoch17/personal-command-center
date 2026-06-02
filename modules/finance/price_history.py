"""Daily price backfill + parquet cache for held / watchlist / benchmark tickers.

Wraps yfinance with an on-disk parquet cache so repeated metric computations
don't re-hit the network. One file per ticker under ``data/price_cache/``.

yfinance (>=0.2) returns a *MultiIndex*-columned frame even for a single ticker
(level 0 = OHLCV field, level 1 = ticker); we flatten that to plain OHLCV here so
downstream code can just do ``df["Close"]``.
"""
from __future__ import annotations

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
    """Most recent available close for a ticker (None if no data)."""
    closes = get_closes(ticker)
    return float(closes.iloc[-1]) if not closes.empty else None
