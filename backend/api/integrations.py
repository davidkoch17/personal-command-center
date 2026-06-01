"""Integrations API — calendar, GitHub, travel, and a diagnostics health check."""
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.api._helpers import clean
from modules.integrations import calendar_ical, github, travel, diagnostics

router = APIRouter()


@router.get("/calendar")
def calendar(days: int = Query(30, ge=1)) -> dict:
    """Upcoming Outlook calendar events within ``days`` (empty if not configured)."""
    if not calendar_ical.is_configured():
        return {"configured": False, "events": []}
    events = []
    for e in calendar_ical.fetch_events(days_ahead=days):
        events.append({
            "title": e.get("title", ""),
            "start": clean(e.get("start")),
            "end": clean(e.get("end")),
            "location": e.get("location", ""),
            "description": e.get("description", ""),
        })
    return {"configured": True, "events": events}


@router.get("/github/commits")
def github_commits(limit: int = Query(10, ge=1)) -> dict:
    """Recent commits across the user's most active repos (empty if not configured)."""
    if not github.is_configured():
        return {"configured": False, "commits": []}
    return {"configured": True, "commits": github.recent_commits(limit=limit)}


@router.get("/travel/upcoming")
def travel_upcoming() -> dict:
    """Upcoming trips parsed from the travel notes, with days-until each."""
    trips = []
    for t in travel.upcoming_trips():
        trips.append({**t, "days_until": travel.days_until(t.get("date", ""))})
    return {"trips": trips}


@router.get("/diagnostics")
def integration_diagnostics() -> dict:
    """Health-check every wired integration (Outlook, GitHub, Alpha Vantage, ...)."""
    return {"checks": diagnostics.run_all()}
