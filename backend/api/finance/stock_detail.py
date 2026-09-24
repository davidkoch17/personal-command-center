"""Single Stock tab endpoints (Chunk 4).

Thin routes over ``modules.finance.stock_detail`` (fundamentals / position /
price series) and ``modules.finance.peers`` (hybrid auto-or-custom peer table).
``/stock-universe`` feeds the tab's selector: current holdings first, then the
vault watchlist.
"""
from __future__ import annotations

import warnings

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

from core.config import DEFAULT_BENCHMARK, get_logger
from modules.finance import peers, positions, stock_detail, watchlist

logger = get_logger(__name__)

router = APIRouter()

# Tickers are upper-case symbols like ADBE, ADS.DE, BTC-USD, BRK-B.
_TICKER = Path(..., pattern=r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,14}$")


@router.get("/stock-universe")
def stock_universe() -> dict:
    """Selector source: held tickers (with names) first, then watchlist tickers not held."""
    held = []
    for ticker in positions.current_holdings():
        meta = positions.get_position(ticker)
        held.append({"ticker": ticker, "name": meta.name if meta else ticker})
    held.sort(key=lambda r: r["ticker"])
    held_set = {h["ticker"].upper() for h in held}

    watch, seen = [], set(held_set)
    for e in watchlist.flat_entries():
        t = e["ticker"].upper()
        # Macro-pulse rows (indices, FX pairs) have no company fundamentals to analyse.
        if t in seen or t.startswith("^") or t.endswith("=X"):
            continue
        seen.add(t)
        watch.append({"ticker": t, "name": e["name"] or t})
    return {"held": held, "watchlist": watch}


@router.get("/stock-detail/{ticker}")
def get_stock_detail(
    ticker: str = _TICKER,
    period: str = Query("1y", pattern="^(1w|1m|3m|ytd|1y|all)$"),
    benchmark: str = Query(DEFAULT_BENCHMARK),
) -> dict:
    """Fundamentals + (if held) position summary + price series for one ticker."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return stock_detail.stock_detail(ticker, period=period, benchmark=benchmark)


@router.get("/peers/{ticker}")
def get_peers(ticker: str = _TICKER) -> dict:
    """Resolved peer table (override -> auto), subject row first, with each peer's metrics."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return peers.peer_table(ticker)


class PeersRequest(BaseModel):
    peers: list[str]  # [] clears the override -> back to auto-derived


@router.patch("/peers/{ticker}")
def patch_peers(req: PeersRequest, ticker: str = _TICKER) -> dict:
    """Save (or, with an empty list, clear) a custom peer list, then return the new table."""
    if len(req.peers) > 50:
        raise HTTPException(status_code=422, detail="too many peers")
    peers.set_override(ticker, req.peers)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return peers.peer_table(ticker)
