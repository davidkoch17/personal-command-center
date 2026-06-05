"""Weekly briefing (Item #16) — generated Sunday 18:00, written to the vault.

Trigger model: the backend runs :func:`scheduler_loop` (started from the FastAPI
lifespan). Every check interval it asks :func:`is_due` whether the most recent
Sunday-18:00 trigger has fired yet (tracked in a repo-local state file, NOT the
vault). If the laptop was off at trigger time, the next backend start catches up.

Output: ``99_System/Briefings/YYYY-MM-DD_briefing.md`` — same naming as the
existing Cowork-written morning briefings, German, Sunday-evening week-ahead
framing.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from core.config import DATA_DIR, SYSTEM_PATH, get_logger
from modules.agents.claude_cli import run_claude
from modules.briefings.context import assemble_briefing_context

logger = get_logger(__name__)

BRIEFINGS_DIR = SYSTEM_PATH / "Briefings"
STATE_FILE = DATA_DIR / "weekly_briefing_state.json"

TRIGGER_WEEKDAY = 6   # Sunday (Monday=0)
TRIGGER_HOUR = 18     # 18:00
CHECK_INTERVAL_S = 30 * 60


def _most_recent_trigger(now: datetime) -> datetime:
    """The latest Sunday-18:00 at or before ``now``."""
    days_back = (now.weekday() - TRIGGER_WEEKDAY) % 7
    candidate = (now - timedelta(days=days_back)).replace(
        hour=TRIGGER_HOUR, minute=0, second=0, microsecond=0
    )
    if candidate > now:
        candidate -= timedelta(days=7)
    return candidate


def _last_generated() -> datetime | None:
    if not STATE_FILE.exists():
        return None
    try:
        raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return datetime.fromisoformat(raw["last_generated"])
    except (ValueError, KeyError, json.JSONDecodeError):
        logger.warning("weekly briefing state unreadable — treating as never run")
        return None


def is_due(now: datetime | None = None) -> bool:
    """True if the most recent Sunday-18:00 trigger has not produced a briefing yet."""
    now = now or datetime.now()
    last = _last_generated()
    return last is None or last < _most_recent_trigger(now)


def generate_weekly_briefing(now: datetime | None = None) -> Path:
    """Generate the weekly briefing and write it to the vault. Returns the path.

    Vault write happens via Python file I/O (OneDrive rule); an existing target
    is backed up to ``.md.bak`` first.
    """
    now = now or datetime.now()
    context = assemble_briefing_context()
    prompt = f"""Du bist Davids Chief of Staff. Es ist Sonntagabend — erstelle sein Wochen-Briefing für die kommende Woche auf Basis des Kontexts unten.

Kontext:
{context}

Format: reines Markdown, KEIN JSON, kein Text davor oder danach. Struktur exakt so:

**<Wochentag>, {now.strftime('%d.%m.%Y')}** — Wochen-Briefing

**Diese Woche im Blick (Top 3):**
1. ...

**Hard Dates:**
- ... (exakte Daten, nie "Ende der Woche")

**Projekte:**
- <folder> — Status + konkreter nächster Schritt

**Fokus-Vorschlag für die Woche:**
<2-4 Sätze: was die Woche entscheidet, womit Montag starten>

Ton: direkt, sachlich, kompetent — kein Fluff, keine Emojis. Nenne wörtliche Projekt-Folder, Ticker, exakte Daten und Task-Texte aus dem Kontext, nie generische Platzhalter. Erfinde nichts, was nicht im Kontext steht.
"""
    output = run_claude(prompt, timeout=300).strip()
    if len(output) < 200:
        raise RuntimeError(
            f"Weekly briefing output suspiciously short ({len(output)} chars) — not writing."
        )

    BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = BRIEFINGS_DIR / f"{now.strftime('%Y-%m-%d')}_briefing.md"
    if path.exists():
        shutil.copy2(path, path.with_suffix(".md.bak"))
    path.write_text(output + "\n", encoding="utf-8")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"last_generated": now.isoformat(), "path": str(path)}, indent=2),
        encoding="utf-8",
    )
    logger.info("weekly briefing written: %s (%d chars)", path, len(output))
    return path


async def scheduler_loop() -> None:
    """Backend-internal cron: check every 30 min, generate when due.

    ``generate_weekly_briefing`` blocks on a ``claude -p`` subprocess for up to
    5 minutes, so it runs in a worker thread to keep the event loop free.
    """
    logger.info("weekly briefing scheduler started (Sunday %02d:00)", TRIGGER_HOUR)
    while True:
        try:
            if is_due():
                logger.info("weekly briefing due — generating")
                await asyncio.to_thread(generate_weekly_briefing)
        except Exception:  # noqa: BLE001 - scheduler must survive any failure
            logger.warning("weekly briefing generation failed", exc_info=True)
        await asyncio.sleep(CHECK_INTERVAL_S)
