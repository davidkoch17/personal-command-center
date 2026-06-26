"""Captures API (Phase D — News Captures Hub + Connected News per position).

Read + triage the captures SQLite store the Phase A pipeline writes. The DB is
the source of truth (screenshots/audio = backup); this layer only adapts the
``modules.captures.db`` query/mutation functions to HTTP.

Approval model B (locked § b): news with a clear ticker auto-surfaces
(``approved-auto``); tasks/park always require review before they hit a queue.
The Captures tab ``pending`` filter is David's triage queue. Routing one item
can also create the downstream task/note/park row.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.config import get_logger
from modules.agents import data_sources
from modules.captures import db

logger = get_logger(__name__)

router = APIRouter()

# A capture cluster (BigMovesBanner rule b): >= 3 captures for one ticker in 48h.
_CLUSTER_MIN = 3
_CLUSTER_WINDOW_H = 48
# A big single-day move (BigMovesBanner rule a): |day move| > 5%.
_BIG_MOVE_PCT = 5.0


class TickerLink(BaseModel):
    ticker: str
    sector: str | None = None


class RouteRequest(BaseModel):
    """Edit a capture's routing then (optionally) approve + create the downstream row."""

    category: str | None = None          # news | task | park | note
    status: str | None = None            # pending | approved | archived | approved-auto
    tickers: list[TickerLink] | None = None
    notes: str | None = None
    approve: bool = False                # if true: status->approved + route by category
    task_text: str | None = None         # used when routing to a Task
    project: str | None = None
    title: str | None = None             # used when routing to Note / Park


@router.get("")
def list_captures(
    status: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(300, ge=1, le=2000),
) -> dict:
    """Captures overview table (newest first), optional status/category filter."""
    items = db.list_captures(status=status, category=category, limit=limit)
    return {
        "captures": items,
        "count": len(items),
        "status_counts": db.status_counts(),
    }


@router.get("/radar")
def radar() -> dict:
    """Watchlist-wide sector radar — capture counts grouped by sector."""
    return {"sectors": db.sector_radar(), "ticker_counts": db.ticker_counts()}


@router.get("/for-ticker/{ticker}")
def for_ticker(ticker: str) -> dict:
    """Connected News for one position: sector summary, big-moves flags, full list.

    Structure is LOCKED (spec § d): sector summary chips, then a big-moves banner
    (day move > 5% OR a >=3-capture/48h cluster), then every linked capture newest
    first (no truncation, no pagination).
    """
    tk = ticker.strip().upper()
    captures = db.captures_for_ticker(tk)

    # Sector summary — counts of this ticker's captures by their tagged sector.
    sector_counts: dict[str, int] = {}
    for c in captures:
        for t in c.get("tickers", []):
            if t["ticker"] == tk:
                sec = t.get("sector") or "Uncategorized"
                sector_counts[sec] = sector_counts.get(sec, 0) + 1
    sectors = [
        {"sector": s, "count": n}
        for s, n in sorted(sector_counts.items(), key=lambda kv: kv[1], reverse=True)
    ]

    # Big move (a): live day move > 5%.
    snap = data_sources.price_snapshot(tk)
    day_move = None if snap.get("error") else snap.get("day_change_pct")
    if day_move is None and not snap.get("error"):
        # Fall back to the ~1w change when no intraday day move is exposed.
        day_move = snap.get("week_change_pct")

    # Cluster (b): >= _CLUSTER_MIN captures within _CLUSTER_WINDOW_H hours.
    cluster = _detect_cluster(captures)

    flags = []
    if day_move is not None and abs(day_move) > _BIG_MOVE_PCT:
        flags.append({
            "type": "day_move",
            "message": f"{tk} moved {day_move:+.1f}% — large single-day move",
            "value": round(day_move, 2),
        })
    if cluster:
        flags.append({
            "type": "cluster",
            "message": f"{cluster} captures for {tk} within {_CLUSTER_WINDOW_H}h — news cluster",
            "value": cluster,
        })

    return {
        "ticker": tk,
        "sectors": sectors,
        "big_moves": flags,
        "day_change_pct": round(day_move, 2) if day_move is not None else None,
        "captures": captures,
        "count": len(captures),
    }


def _detect_cluster(captures: list[dict]) -> int:
    """Largest count of captures falling inside any rolling 48h window (0 if < min)."""
    times: list[datetime] = []
    for c in captures:
        raw = c.get("captured_at")
        if not raw:
            continue
        try:
            times.append(datetime.fromisoformat(str(raw).replace("Z", "+00:00")).replace(tzinfo=None))
        except ValueError:
            continue
    times.sort()
    window = timedelta(hours=_CLUSTER_WINDOW_H)
    best = 0
    for i, start in enumerate(times):
        n = sum(1 for t in times[i:] if t - start <= window)
        best = max(best, n)
    return best if best >= _CLUSTER_MIN else 0


@router.get("/{capture_id}")
def get_capture(capture_id: str) -> dict:
    """Full detail for one capture (OCR text / transcript / routing / tickers)."""
    item = db.get_capture(capture_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"capture not found: {capture_id}")
    return item


@router.post("/{capture_id}/route")
def route_capture(capture_id: str, req: RouteRequest) -> dict:
    """Edit routing, then optionally approve + create the downstream task/note/park row.

    Re-classification (changing ``category``) and unlinking/relinking tickers are
    both supported — David can re-triage anything afterwards (spec § b).
    """
    capture = db.get_capture(capture_id)
    if capture is None:
        raise HTTPException(status_code=404, detail=f"capture not found: {capture_id}")

    category = req.category or capture.get("category")
    status = req.status
    if req.approve:
        status = "approved"

    if req.tickers is not None:
        db.replace_tickers(capture_id, [t.model_dump() for t in req.tickers])

    db.update_capture(
        capture_id,
        category=req.category,
        status=status,
        notes=req.notes,
        routing_locked=1 if req.approve else None,
    )

    routed: dict | None = None
    if req.approve:
        routed = _route_downstream(capture_id, category, capture, req)

    return {"ok": True, "capture_id": capture_id, "status": status, "routed": routed}


def _route_downstream(capture_id: str, category: str | None, capture: dict,
                      req: RouteRequest) -> dict | None:
    """Create the task/note/park row implied by an approved capture's category."""
    body = capture.get("ocr_text") or capture.get("voice_transcript") or ""
    title = req.title or capture.get("topic_tag") or capture.get("topic_slug") or "capture"
    if category == "task":
        text = req.task_text or title
        row_id = db.insert_task(text, req.project, capture_id)
        return {"kind": "task", "id": row_id}
    if category == "park":
        row_id = db.insert_park(title, body, capture_id)
        return {"kind": "park", "id": row_id}
    if category == "note":
        row_id = db.insert_note(title, body, capture.get("ai_tags"), capture_id)
        return {"kind": "note", "id": row_id}
    # category == "news" (or unset): nothing downstream — it lives as a capture.
    return None
