"""Watchlist persistence backed by a repo-local JSON file (data/watchlist.json).

Seeded with Nike on first use. Lives in the repo, not the vault — these are
dashboard-generated records, not Excel source data.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from core.config import WATCHLIST_FILE

logger = logging.getLogger(__name__)

VALID_STATUSES = ["researching", "considering", "paused", "exited"]

SEED: list[dict] = [
    {"ticker": "NKE", "name": "Nike", "status": "researching", "notes": "research pending"},
]


def load(path: Path = WATCHLIST_FILE) -> list[dict]:
    """Load watchlist items. If no file exists yet, return the Nike seed."""
    if not path.exists():
        return list(SEED)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        logger.warning("watchlist.json is not a list; ignoring.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read %s: %s", path, exc)
    return list(SEED)


def _save(items: list[dict], path: Path = WATCHLIST_FILE) -> None:
    """Write the full watchlist list to JSON (repo dir; Write tool not used)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def add(ticker: str, name: str = "", status: str = "researching",
        notes: str = "", path: Path = WATCHLIST_FILE) -> list[dict]:
    """Add (or update) a watchlist entry keyed by ticker; return the new list.

    Seeds from the current list (file or Nike default) so the first add
    persists the seed entries too. Raises ValueError on empty ticker.
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("Ticker is required.")
    if status not in VALID_STATUSES:
        status = "researching"

    items = load(path)
    entry = {
        "ticker": ticker,
        "name": name.strip(),
        "status": status,
        "notes": notes.strip(),
    }
    # Replace existing entry with the same ticker, else append.
    for i, it in enumerate(items):
        if str(it.get("ticker", "")).strip().upper() == ticker:
            items[i] = entry
            break
    else:
        items.append(entry)

    _save(items, path)
    return items
