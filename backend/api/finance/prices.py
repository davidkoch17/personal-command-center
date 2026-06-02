"""Price history + returns endpoints (Phase 15a)."""
from __future__ import annotations

import warnings

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from core.config import get_logger
from modules.finance.price_history import backfill_history, get_returns

logger = get_logger(__name__)

router = APIRouter()


@router.get("/prices/{ticker}")
def prices(ticker: str, days: int = Query(365, ge=1, le=3650)) -> dict:
    """Daily close history for ``ticker`` over the last ``days`` days."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = backfill_history(ticker)
    if df.empty or "Close" not in df.columns:
        raise HTTPException(status_code=404, detail=f"No price history for {ticker}")
    closes = df["Close"].dropna().tail(days)
    series = [
        {"date": pd.Timestamp(idx).date().isoformat(), "close": round(float(val), 4)}
        for idx, val in closes.items()
    ]
    return {"ticker": ticker, "points": series, "count": len(series)}


@router.get("/returns/{ticker}")
def returns(ticker: str, freq: str = Query("D", pattern="^[DWM]$")) -> dict:
    """Periodic returns for ``ticker`` (freq = D | W | M)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = get_returns(ticker, freq=freq)  # type: ignore[arg-type]
    if r.empty:
        raise HTTPException(status_code=404, detail=f"No returns for {ticker}")
    series = [
        {"date": pd.Timestamp(idx).date().isoformat(), "return": round(float(val), 6)}
        for idx, val in r.items()
    ]
    return {"ticker": ticker, "freq": freq, "returns": series, "count": len(series)}
