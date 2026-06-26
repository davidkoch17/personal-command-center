"""Daily net-worth snapshot scheduler (Phase G).

Mirrors the weekly-briefing scheduler: the backend runs :func:`scheduler_loop`
from its FastAPI lifespan, checking every 30 min whether the most recent
18:00 trigger has produced a snapshot yet (tracked in a repo-local state file,
NOT the vault). If the laptop was off at 18:00, the next backend start catches
up. This replaces a fragile Windows Task Scheduler entry with the same in-repo
pattern the weekly briefing already uses — the backend autostarts windowless on
login, so "laptop on = snapshots happen".

``run_snapshot`` is idempotent (upserts on the date key), so a catch-up run that
fires the next morning simply writes today's row with current prices.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta

from core.config import DATA_DIR, get_logger
from modules.finance.daily_snapshot import run_snapshot

logger = get_logger(__name__)

STATE_FILE = DATA_DIR / "daily_snapshot_state.json"

TRIGGER_HOUR = 18          # 18:00 local
CHECK_INTERVAL_S = 30 * 60  # re-check every 30 min


def _most_recent_trigger(now: datetime) -> datetime:
    """The latest HH:00 trigger at or before ``now`` (today's, else yesterday's)."""
    candidate = now.replace(hour=TRIGGER_HOUR, minute=0, second=0, microsecond=0)
    if candidate > now:
        candidate -= timedelta(days=1)
    return candidate


def _last_run() -> datetime | None:
    if not STATE_FILE.exists():
        return None
    try:
        raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return datetime.fromisoformat(raw["last_run"])
    except (ValueError, KeyError, json.JSONDecodeError):
        logger.warning("daily snapshot state unreadable — treating as never run")
        return None


def is_due(now: datetime | None = None) -> bool:
    """True if the most recent 18:00 trigger has not produced a snapshot yet."""
    now = now or datetime.now()
    last = _last_run()
    return last is None or last < _most_recent_trigger(now)


def _record_run(now: datetime) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"last_run": now.isoformat()}, indent=2), encoding="utf-8"
    )


async def scheduler_loop() -> None:
    """Backend-internal cron: check every 30 min, run the snapshot when due.

    ``run_snapshot`` blocks on yfinance network calls, so it runs in a worker
    thread to keep the event loop free.
    """
    logger.info("daily snapshot scheduler started (%02d:00)", TRIGGER_HOUR)
    while True:
        try:
            if is_due():
                logger.info("daily snapshot due — running")
                await asyncio.to_thread(run_snapshot)
                _record_run(datetime.now())
        except Exception:  # noqa: BLE001 - scheduler must survive any failure
            logger.warning("daily snapshot failed", exc_info=True)
        await asyncio.sleep(CHECK_INTERVAL_S)
