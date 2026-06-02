"""Behavioral / journal endpoints (Phase 15d, Category H).

Decision journal (log + list + retrospective), hypothesis hit-rate review, and
the anti-portfolio of skipped names. All storage is Markdown in the vault, via
``modules.finance.decision_journal`` / ``hypothesis_review`` / ``anti_portfolio``.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config import get_logger
from modules.finance import anti_portfolio as ap
from modules.finance import decision_journal as dj
from modules.finance import hypothesis_review as hr

logger = get_logger(__name__)

router = APIRouter()


class DecisionRequest(BaseModel):
    ticker: str
    action: str  # buy / sell / add / trim
    quantity: float
    price: float
    rationale: str
    conviction_score: int
    emotion: str
    expected_return: float | None = None
    expected_timeframe_months: int | None = None
    thesis: str = ""
    risks: str = ""
    pre_mortem: str = ""


class RetrospectiveRequest(BaseModel):
    retro_text: str
    was_right: bool


class SkipRequest(BaseModel):
    ticker: str
    name: str = ""
    considered_date: date | None = None
    price: float = 0.0
    bull_case: str = ""
    bear_case: str = ""
    reason: str = ""


@router.post("/journal/decision")
def log_decision(req: DecisionRequest) -> dict:
    """Log a decision (full structured doc) to the vault decision journal."""
    path = dj.log_decision(
        ticker=req.ticker,
        action=req.action,
        quantity=req.quantity,
        price=req.price,
        rationale=req.rationale,
        conviction_score=req.conviction_score,
        emotion=req.emotion,
        expected_return=req.expected_return,
        expected_timeframe_months=req.expected_timeframe_months,
        thesis=req.thesis,
        risks=req.risks,
        pre_mortem=req.pre_mortem,
    )
    return {"ok": True, "filename": path.name, "path": str(path)}


@router.get("/journal/decisions")
def list_decisions(limit: int = 50) -> dict:
    """Recent decisions parsed into structured form (newest first)."""
    items = dj.list_decisions(limit=limit)
    return {"decisions": items, "count": len(items)}


@router.get("/journal/decision/{filename}")
def get_decision(filename: str) -> dict:
    """Full markdown + parsed header for one decision file."""
    item = dj.get_decision(filename)
    if item is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return item


@router.post("/journal/{filename}/retrospective")
def add_retrospective(filename: str, req: RetrospectiveRequest) -> dict:
    """Fill in the retrospective section of an existing decision file."""
    ok = dj.add_retrospective(filename, req.retro_text, req.was_right)
    if not ok:
        raise HTTPException(status_code=404, detail="decision not found")
    return {"ok": True, "filename": filename}


@router.get("/journal/hit-rate")
def hit_rate(quarters_back: int = 4) -> dict:
    """Aggregate hypothesis hit rate from closed hypotheses."""
    return hr.hit_rate_review(quarters_back=quarters_back)


@router.get("/journal/anti-portfolio")
def anti_portfolio() -> dict:
    """Names considered but not bought + the annual-review-due subset."""
    skips = ap.list_skips()
    return {"skips": skips, "count": len(skips), "review_due": ap.annual_review()}


@router.post("/journal/anti-portfolio")
def log_skip(req: SkipRequest) -> dict:
    """Log a ticker that was considered but skipped."""
    ap.log_skip(
        ticker=req.ticker,
        name=req.name,
        considered_date=req.considered_date or date.today(),
        price=req.price,
        bull_case=req.bull_case,
        bear_case=req.bear_case,
        reason=req.reason,
    )
    return {"ok": True, "ticker": req.ticker}
