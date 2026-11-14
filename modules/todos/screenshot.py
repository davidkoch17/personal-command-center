"""Turn a pasted screenshot of a to-do list into proposed tasks.

Flow: the browser sends the image (base64) → saved to a temp file under
``data/todo_imports/`` → ``claude -p`` reads it with the Read tool (Claude
can read images) and returns JSON → proposals are cleaned and validated
against the schema → the temp file is deleted. Nothing is written to
``todos.json`` here: the UI shows the proposals and the user confirms, then
``store.create_tasks`` writes them in one go.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from core.config import DATA_DIR, get_logger
from modules.agents.claude_cli import run_claude
from modules.todos.store import AREAS, DEFAULT_AREA, TodoError

logger = get_logger(__name__)

IMPORT_DIR = DATA_DIR / "todo_imports"
MAX_BYTES = 8 * 1024 * 1024  # 8 MB is plenty for a screenshot
_EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}


def _prompt(image_path: Path) -> str:
    today = date.today().isoformat()
    return f"""Read the image file at: {image_path}

It is a screenshot of a to-do list (any app, handwriting or notes; may be German or English).
Extract every to-do item you can see. Today is {today}.

Return ONLY a JSON array, no prose, no code fences. Each element:
{{"title": "<short task title, keep the original language and wording>",
  "area": "<one of: {', '.join(AREAS)}>",
  "priority": <1 = urgent, 2 = normal, 3 = someday>,
  "due": "<YYYY-MM-DD if a date or weekday is visible, resolved relative to today, else null>",
  "subtasks": ["<indented or nested items under this task, if any>"],
  "done": <true if the item is visibly ticked/crossed out, else false>}}

Rules: skip headings that are not tasks; never invent items; if nothing readable, return [].
Never include card numbers, passwords or codes even if visible."""


def _parse_json_array(text: str) -> list[Any]:
    """Pull the first JSON array out of the model's answer."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end < start:
        raise TodoError("Claude did not return a to-do list for this image")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise TodoError("could not read Claude's answer as JSON") from exc
    if not isinstance(data, list):
        raise TodoError("unexpected answer format")
    return data


def _clean(item: Any) -> dict[str, Any] | None:
    """Normalize one proposal to valid store fields (or drop it)."""
    if not isinstance(item, dict):
        return None
    title = str(item.get("title") or "").strip()
    if not title:
        return None
    area = item.get("area") if item.get("area") in AREAS else DEFAULT_AREA
    try:
        priority = min(3, max(1, int(item.get("priority") or 2)))
    except (TypeError, ValueError):
        priority = 2
    due = item.get("due")
    try:
        due = date.fromisoformat(str(due)).isoformat() if due else None
    except ValueError:
        due = None
    subs = [
        {"title": str(s).strip(), "done": False}
        for s in (item.get("subtasks") or [])
        if str(s).strip()
    ]
    return {
        "title": title[:200],
        "area": area,
        "priority": priority,
        "due": due,
        "subtasks": subs,
        "done_in_image": bool(item.get("done")),
    }


def extract_todos(image_b64: str, mime: str) -> list[dict[str, Any]]:
    """Return proposed tasks read from a base64 image. Raises TodoError."""
    ext = _EXT.get(mime)
    if not ext:
        raise TodoError(f"unsupported image type {mime!r} (png, jpeg, webp, gif)")
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise TodoError("image data is not valid base64") from exc
    if len(raw) > MAX_BYTES:
        raise TodoError("image is larger than 8 MB")

    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = IMPORT_DIR / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(raw)
    try:
        answer = run_claude(_prompt(path.resolve()), timeout=180, allowed_tools=["Read"])
    finally:
        path.unlink(missing_ok=True)

    proposals = [p for p in (_clean(i) for i in _parse_json_array(answer)) if p]
    logger.info("todos: screenshot import proposed %d tasks", len(proposals))
    return proposals
