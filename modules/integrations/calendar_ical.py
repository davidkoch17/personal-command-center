"""Read Outlook calendar via published iCal URL.

Degrades gracefully: returns an empty list when ``OUTLOOK_ICAL_URL`` is unset,
the fetch fails, or the ``icalendar`` / ``recurring-ical-events`` libraries are
not installed. Heavy third-party imports are lazy (inside the function) so the
module always imports cleanly.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from core.config import get_logger

logger = get_logger(__name__)


def is_configured() -> bool:
    """True when the published iCal URL is present in the environment."""
    return bool(os.getenv("OUTLOOK_ICAL_URL"))


def fetch_events(days_ahead: int = 30) -> list[dict]:
    """Return upcoming events as ``[{title, start, end, location, description}, ...]``."""
    url = os.getenv("OUTLOOK_ICAL_URL")
    if not url:
        return []
    try:
        import requests
        from icalendar import Calendar
        import recurring_ical_events

        r = requests.get(url, timeout=15)
        cal = Calendar.from_ical(r.text)
        start = datetime.now()
        end = start + timedelta(days=days_ahead)
        events = recurring_ical_events.of(cal).between(start, end)
    except Exception as e:  # noqa: BLE001 - any failure -> degrade to no events
        logger.warning("calendar fetch_events failed: %s", e)
        return []

    out: list[dict] = []
    for ev in events:
        dtstart = ev.get("dtstart")
        dtend = ev.get("dtend")
        out.append(
            {
                "title": str(ev.get("summary", "")),
                "start": dtstart.dt if dtstart else None,
                "end": dtend.dt if dtend else None,
                "location": str(ev.get("location", "")),
                "description": str(ev.get("description", ""))[:500],
            }
        )
    return sorted(out, key=lambda e: str(e["start"]))


def next_events(n: int = 5) -> list[dict]:
    """Return the next ``n`` events within the coming 30 days."""
    return fetch_events(days_ahead=30)[:n]
