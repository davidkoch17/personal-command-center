"""Priorities API — recommends an order for clustered upcoming deadlines.

Unlike the long-running background skills, this runs the Priority Suggestor
synchronously (a single bounded ``claude -p`` call). FastAPI executes the sync
handler in its threadpool, so the event loop is not blocked while Claude thinks.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/suggest")
def suggest_priority(days: int = 14) -> dict:
    """Return a ranked recommendation for deadlines within ``days`` days."""
    from modules.agents.skills.priority_suggestor import suggest

    return suggest(days_horizon=days)
