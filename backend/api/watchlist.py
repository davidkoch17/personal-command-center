"""Watchlist API — universe + per-ticker dossiers (Finance_Tracker-independent)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.models.schemas import WatchlistAddRequest, WatchlistHypothesisRequest
from modules.finance import watchlist
from modules.finance import portfolio_skills
from modules.agents import data_sources
from modules.investing import research

router = APIRouter()


@router.get("")
def list_watchlist(prices: bool = Query(True)) -> dict:
    """Watchlist names grouped by tier, optionally with live price snapshots."""
    items = watchlist.load()
    grouped: dict[str, list[dict]] = {}
    for it in items:
        tk = str(it.get("ticker", "")).upper()
        entry = {
            "ticker": tk,
            "name": it.get("name", ""),
            "status": it.get("status", ""),
            "tier": it.get("tier", "Untagged"),
            "added": it.get("added"),
            "notes": it.get("notes", ""),
        }
        if prices and tk:
            snap = data_sources.price_snapshot(tk)
            entry["price"] = None if "error" in snap else {
                "last_close": snap.get("last_close"),
                "week_change_pct": snap.get("week_change_pct"),
                "month_change_pct": snap.get("month_change_pct"),
                "currency": snap.get("currency"),
            }
        grouped.setdefault(entry["tier"], []).append(entry)
    return {"tiers": grouped, "count": len(items), "valid_statuses": watchlist.VALID_STATUSES}


@router.post("")
def add_ticker(req: WatchlistAddRequest) -> dict:
    """Add a name to the watchlist (annotates tier + added-date, then persists)."""
    try:
        items = watchlist.add(
            ticker=req.ticker, name=req.name, status=req.status, notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    tk = req.ticker.strip().upper()
    for it in items:
        if str(it.get("ticker", "")).upper() == tk:
            it["tier"] = req.tier
            it.setdefault("added", date.today().isoformat())
    watchlist._save(items)
    return {"ok": True, "ticker": tk}


@router.get("/{ticker}")
def dossier(ticker: str) -> dict:
    """Per-ticker dossier: price, news, filings, hypotheses, signals, position note."""
    tk = ticker.strip().upper()
    items = watchlist.load()
    meta = next((i for i in items if str(i.get("ticker", "")).upper() == tk), {})
    name = meta.get("name", "")
    snap = data_sources.price_snapshot(tk)
    return {
        "ticker": tk,
        "name": name,
        "status": meta.get("status"),
        "tier": meta.get("tier"),
        "price": None if "error" in snap else snap,
        "news": data_sources.combined_news(tk, limit=8),
        "filings": data_sources.sec_filings(tk),
        "hypotheses": research.filter_hypotheses(tk, name),
        "signals": research.recent_signals(tk, name, limit=8),
        "position_note": research.read_position_note(tk),
    }


@router.post("/{ticker}/hypothesis")
def add_hypothesis(ticker: str, req: WatchlistHypothesisRequest) -> dict:
    """Append a hypothesis for this ticker to the Hypothesis_Tracker (fast, synchronous)."""
    tk = ticker.strip().upper()
    if not req.hypothesis.strip():
        raise HTTPException(status_code=400, detail="Hypothesis text is required.")
    message = portfolio_skills.add_hypothesis(tk, req.hypothesis.strip())
    return {"ok": True, "message": message}
