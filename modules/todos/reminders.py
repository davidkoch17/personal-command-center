"""Due-date reminders for todos.json, pushed to David's iPhone via ntfy.

Every evening at 18:00 (backend lifespan loop, same pattern as the daily
snapshot) a digest of open tasks that are overdue, due today, due tomorrow or
due within the next 7 days is sent as one push notification. If the laptop was
off at 18:00, the next backend start catches up once. Nothing is sent when
there is nothing due.

Transport: ntfy (https://ntfy.sh) — a plain HTTP POST to a secret topic; the
iPhone ntfy app subscribed to that topic shows the push. Only task titles and
due dates leave the machine, never notes. Configure with ``NTFY_TOPIC`` (and
optionally ``NTFY_SERVER``) in ``.env``; without a topic the loop stays idle.
"""
from __future__ import annotations

import asyncio
import base64
import json
from datetime import date, datetime, timedelta
from typing import Any

import requests

from core.config import DATA_DIR, NTFY_SERVER, NTFY_TOPIC, get_logger
from modules.todos import store

logger = get_logger(__name__)

STATE_FILE = DATA_DIR / "todo_reminder_state.json"
TRIGGER_HOUR = 18           # 18:00 local — evening digest for the coming days
CHECK_INTERVAL_S = 15 * 60  # re-check every 15 min
SOON_DAYS = 7


# --- Digest --------------------------------------------------------------------
def build_digest(tasks: list[dict[str, Any]], today: date | None = None) -> dict[str, list[dict]]:
    """Group open dated tasks into overdue / today / tomorrow / soon."""
    today = today or date.today()
    groups: dict[str, list[dict]] = {"overdue": [], "today": [], "tomorrow": [], "soon": []}
    for t in tasks:
        if t.get("status") == "done" or not t.get("due"):
            continue
        try:
            days = (date.fromisoformat(t["due"]) - today).days
        except ValueError:
            continue
        key = (
            "overdue" if days < 0
            else "today" if days == 0
            else "tomorrow" if days == 1
            else "soon" if days <= SOON_DAYS
            else None
        )
        if key:
            groups[key].append({"title": t.get("title", ""), "due": t["due"], "days": days})
    for items in groups.values():
        items.sort(key=lambda i: i["due"])
    return groups


def format_digest(groups: dict[str, list[dict]]) -> tuple[str, str] | None:
    """(title, body) for the push, or None when nothing is due."""
    labels = {
        "overdue": "Überfällig",
        "today": "Heute fällig",
        "tomorrow": "Morgen fällig",
        "soon": f"Nächste {SOON_DAYS} Tage",
    }
    lines: list[str] = []
    for key, label in labels.items():
        items = groups.get(key) or []
        if not items:
            continue
        lines.append(f"{label}:")
        for i in items:
            suffix = f" ({-i['days']}d)" if key == "overdue" else (
                f" ({i['due'][8:10]}.{i['due'][5:7]}.)" if key == "soon" else ""
            )
            lines.append(f"• {i['title']}{suffix}")
        lines.append("")
    if not lines:
        return None
    n_urgent = len(groups["overdue"]) + len(groups["today"]) + len(groups["tomorrow"])
    title = f"To-dos: {n_urgent} dringend" if n_urgent else "To-dos: diese Woche fällig"
    return title, "\n".join(lines).strip()


# --- Transport -----------------------------------------------------------------
def configured() -> bool:
    return bool(NTFY_TOPIC)


def send_push(title: str, body: str, urgent: bool = False) -> None:
    """POST one notification to the ntfy topic. Raises on failure."""
    if not NTFY_TOPIC:
        raise RuntimeError("NTFY_TOPIC is not set in .env")
    resp = requests.post(
        f"{NTFY_SERVER.rstrip('/')}/{NTFY_TOPIC}",
        data=body.encode("utf-8"),
        headers={
            # Header values must be latin-1; ntfy accepts RFC 2047 for UTF-8.
            "Title": "=?UTF-8?B?" + base64.b64encode(title.encode()).decode() + "?=",
            "Priority": "high" if urgent else "default",
            "Tags": "spiral_calendar_pad",
        },
        timeout=15,
    )
    resp.raise_for_status()


def send_digest(today: date | None = None, force: bool = False) -> dict[str, Any]:
    """Build and send today's digest. Returns what happened (for the API/UI)."""
    groups = build_digest(store.load()["tasks"], today)
    msg = format_digest(groups)
    if msg is None and not force:
        return {"sent": False, "reason": "nothing due", "groups": groups}
    title, body = msg or ("To-dos: Test", "Nichts fällig — Benachrichtigungen funktionieren.")
    send_push(title, body, urgent=bool(groups["overdue"] or groups["today"]))
    logger.info("todos: reminder sent (%s)", title)
    return {"sent": True, "title": title, "body": body, "groups": groups}


# --- Scheduler -----------------------------------------------------------------
def _most_recent_trigger(now: datetime) -> datetime:
    candidate = now.replace(hour=TRIGGER_HOUR, minute=0, second=0, microsecond=0)
    return candidate if candidate <= now else candidate - timedelta(days=1)


def _last_run() -> datetime | None:
    try:
        return datetime.fromisoformat(json.loads(STATE_FILE.read_text(encoding="utf-8"))["last_run"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None


def status() -> dict[str, Any]:
    last = _last_run()
    now = datetime.now()
    nxt = _most_recent_trigger(now) + timedelta(days=1)
    return {
        "configured": configured(),
        "server": NTFY_SERVER,
        "topic": NTFY_TOPIC or None,
        "trigger": f"{TRIGGER_HOUR:02d}:00",
        "last_run": last.isoformat() if last else None,
        "next_run": nxt.isoformat(),
    }


def is_due(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    last = _last_run()
    return last is None or last < _most_recent_trigger(now)


def _record_run(now: datetime) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"last_run": now.isoformat()}, indent=2), encoding="utf-8")


async def scheduler_loop() -> None:
    """Backend-internal cron: send the evening digest once per day."""
    logger.info("todo reminder scheduler started (%02d:00, ntfy %s)",
                TRIGGER_HOUR, "on" if configured() else "off — NTFY_TOPIC unset")
    while True:
        try:
            if configured() and is_due():
                await asyncio.to_thread(send_digest)
                _record_run(datetime.now())
        except Exception:  # noqa: BLE001 - scheduler must survive any failure
            logger.warning("todo reminder failed", exc_info=True)
        await asyncio.sleep(CHECK_INTERVAL_S)
