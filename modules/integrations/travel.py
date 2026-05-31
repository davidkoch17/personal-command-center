"""Read trips from 2_Personal/06_Travel/Trips.md."""
from __future__ import annotations

import re
from datetime import date

from core.config import VAULT_PATH, get_logger

logger = get_logger(__name__)

TRIPS_FILE = VAULT_PATH / "2_Personal" / "06_Travel" / "Trips.md"


def upcoming_trips() -> list[dict]:
    """Parse the ``## Upcoming`` section into trip dicts.

    Returns ``[{date, destination, details: [...]}, ...]`` in file order.
    """
    if not TRIPS_FILE.exists():
        return []
    try:
        text = TRIPS_FILE.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("travel read failed: %s", e)
        return []

    out: list[dict] = []
    in_section = False
    current = None
    for line in text.splitlines():
        if line.startswith("## Upcoming"):
            in_section = True
            continue
        if line.startswith("## ") and in_section:
            break
        if in_section and line.startswith("### "):
            if current:
                out.append(current)
            # Accept both em-dash and hyphen separators.
            m = re.match(r"### (\d{4}-\d{2}-\d{2})\s*[—-]\s*(.+)", line)
            if m:
                current = {"date": m.group(1), "destination": m.group(2).strip(), "details": []}
            else:
                current = None
        elif in_section and current and line.strip().startswith("- "):
            current["details"].append(line.strip()[2:])
    if current:
        out.append(current)
    return out


def days_until(iso_date: str) -> int | None:
    """Whole days from today until ``iso_date`` (negative if past)."""
    try:
        target = date.fromisoformat(iso_date)
    except ValueError:
        return None
    return (target - date.today()).days
