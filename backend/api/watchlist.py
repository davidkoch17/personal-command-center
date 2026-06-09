"""Watchlist API — sourced from the vault ``Watchlist.md`` (single source of truth).

GET returns the full tier + theme-section (A–N) structure parsed from
``Watchlist.md`` — the same file the Market Researcher agent reads — so the
dashboard and the agent can never drift. POST appends a bullet to that markdown
(default the Ad-hoc section).
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException

from backend.models.schemas import WatchlistAddRequest, WatchlistHypothesisRequest
from core.config import get_logger
from modules.finance import watchlist
from modules.finance import portfolio_skills
from modules.agents import data_sources
from modules.investing import research

logger = get_logger(__name__)

router = APIRouter()

# Price snapshots are live yfinance calls (~1s each). With ~45 tickers a naive
# serial fetch on every page load is unacceptable, so snapshots are fetched
# concurrently and cached with a short TTL (warm loads are instant).
_SNAP_CACHE: dict[str, tuple[float, dict]] = {}
_SNAP_TTL = 600  # seconds


def _cached_snapshot(ticker: str) -> dict:
    now = time.time()
    hit = _SNAP_CACHE.get(ticker)
    if hit and now - hit[0] < _SNAP_TTL:
        return hit[1]
    snap = data_sources.price_snapshot(ticker)
    _SNAP_CACHE[ticker] = (now, snap)
    return snap


def _price_snapshots(tickers: list[str]) -> dict[str, dict]:
    """Concurrent (cached) price snapshots for many tickers, keyed by ticker."""
    if not tickers:
        return {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        return dict(zip(tickers, ex.map(_cached_snapshot, tickers)))


def _price_field(snap: dict | None) -> dict | None:
    """Trim a raw snapshot to the price fields the card/macro UI consumes."""
    if not snap or "error" in snap:
        return None
    return {
        "last_close": snap.get("last_close"),
        "week_change_pct": snap.get("week_change_pct"),
        "month_change_pct": snap.get("month_change_pct"),
        "currency": snap.get("currency"),
    }


@router.get("")
def list_watchlist(prices: bool = True) -> dict:
    """Full watchlist universe from ``Watchlist.md``, grouped by tier + section.

    Returns ``sections`` (ordered, each with its ticker + note entries) plus a
    ``tiers`` map (kept for the tier filter / macro tab) and ``form_sections``
    (append targets for the add dialog). With ``prices=True`` each ticker entry
    gets a live (cached) price snapshot attached.
    """
    data = watchlist.parse_watchlist_md()
    sections = data["sections"]

    if prices:
        tickers = [e["ticker"] for sec in sections for e in sec["entries"] if e["is_ticker"]]
        snaps = _price_snapshots(tickers)
        for sec in sections:
            for e in sec["entries"]:
                e["price"] = _price_field(snaps.get(e["ticker"])) if e["is_ticker"] else None
    else:
        for sec in sections:
            for e in sec["entries"]:
                e["price"] = None

    # Backward-compatible tier map (filter strip + macro tab read this).
    tiers: dict[str, list[dict]] = {}
    for sec in sections:
        for e in sec["entries"]:
            if e["is_ticker"]:
                tiers.setdefault(e["tier"], []).append(e)

    return {
        "sections": sections,
        "tiers": tiers,
        "count": data["count"],
        "form_sections": watchlist.form_sections(),
        "source": "Watchlist.md (vault)",
    }


@router.post("")
def add_ticker(req: WatchlistAddRequest) -> dict:
    """Append a name to ``Watchlist.md`` under the chosen section (default Ad-hoc).

    Returns ``{ok: False, reason: "already present"}`` (HTTP 200) when the ticker
    is already in the file, so the UI can surface a graceful message instead of
    treating it as an error.
    """
    try:
        result = watchlist.append_entry(
            ticker=req.ticker, name=req.name, notes=req.notes, section_key=req.section or "adhoc",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@router.get("/{ticker}")
def dossier(ticker: str) -> dict:
    """Per-ticker dossier: price, news, filings, hypotheses, signals, position note.

    Name/tier/status metadata is resolved from ``Watchlist.md`` so it matches the
    list view; the rest is pulled live from the data sources.
    """
    tk = ticker.strip().upper()
    meta = next((e for e in watchlist.flat_entries() if e["ticker"].upper() == tk), {})
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
    """Append a hypothesis for this ticker to the Hypothesis_Tracker (fast, synchronous).

    Accepts either ``hypothesis`` (watchlist UI) or ``text`` (Jarvis voice hook).
    """
    tk = ticker.strip().upper()
    statement = (req.hypothesis or req.text).strip()
    if not statement:
        raise HTTPException(status_code=400, detail="Hypothesis text is required.")
    message = portfolio_skills.add_hypothesis(tk, statement)
    return {"ok": True, "message": message}
