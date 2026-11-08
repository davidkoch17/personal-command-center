"""Read/write layer for ``todos.json`` — the single source of truth for the
Personal Admin to-do tracker.

The same file is edited by the dashboard *and* by chat-Claude (OneDrive
connector), so every write follows the same protocol:

1. Re-read the file from disk (never trust an in-memory copy).
2. Apply a small, targeted change to that fresh copy — unknown fields on the
   document, tasks and subtasks are left untouched.
3. Copy the current file to ``todos.backup.json``.
4. Stamp ``updated`` and write atomically (temp file + ``os.replace``).

Plain Python file I/O only (see CLAUDE.md: vault writes never go through the
editor tools).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Callable

from core.config import TODOS_FILE, get_logger

logger = get_logger(__name__)

STATUSES = ("open", "in_progress", "waiting", "done")
# Fixed area list (schema v1, see CLAUDE.md "To-do-Tracker"). Extend here — the
# API exposes it to the UI dropdown.
AREAS = (
    "Banking", "Wohnung", "Versicherung", "Rechnungen",
    "Business", "Career", "Investing", "Other",
)
DEFAULT_AREA = "Other"
PRIORITY_MIN, PRIORITY_MAX = 1, 3
SCHEMA_VERSION = 1

_LOCK = threading.Lock()

# Light guard against sensitive data landing in a synced file: Luhn-valid card
# numbers (13–19 digits, optionally spaced/dashed). Passwords / activation codes
# can't be detected reliably — that rule stays a convention. Payee IBANs are
# allowed (payment to-dos need them).
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?\b")


class TodoError(ValueError):
    """Invalid to-do operation (unknown id, bad field value, sensitive data)."""


# --- File I/O ----------------------------------------------------------------
def _path() -> Path:
    return Path(TODOS_FILE)


def _backup_path(path: Path) -> Path:
    return path.with_name(path.stem + ".backup.json")


def _empty_doc() -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "updated": date.today().isoformat(), "tasks": []}


def load() -> dict[str, Any]:
    """Return the current document from disk (an empty doc if the file is missing)."""
    path = _path()
    if not path.exists():
        logger.warning("todos file not found at %s — returning empty doc", path)
        return _empty_doc()
    with path.open("r", encoding="utf-8-sig") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict):
        raise TodoError(f"{path} does not contain a JSON object")
    doc.setdefault("tasks", [])
    return doc


def _write(doc: dict[str, Any]) -> None:
    """Back up the existing file, then write ``doc`` atomically."""
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, _backup_path(path))
    doc["updated"] = date.today().isoformat()
    fd, tmp = tempfile.mkstemp(prefix=".todos-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _mutate(fn: Callable[[dict[str, Any]], Any]) -> Any:
    """Re-read the file, apply ``fn`` to the fresh doc, write it back."""
    with _LOCK:
        doc = load()
        result = fn(doc)
        _write(doc)
        return result


# --- Validation helpers ------------------------------------------------------
def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def _looks_sensitive(text: str) -> bool:
    text = _IBAN_RE.sub(" ", text)  # IBAN digits can pass Luhn by chance
    # Luhn check keeps phone numbers / reference numbers from tripping the guard.
    return any(
        _luhn_ok(re.sub(r"\D", "", m.group())) for m in _CARD_RE.finditer(text)
    )


def _check_sensitive(*texts: Any) -> None:
    for text in texts:
        if isinstance(text, str) and _looks_sensitive(text):
            raise TodoError(
                "looks like a card number — sensitive data doesn't belong in todos.json"
            )


def _clean_due(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise TodoError(f"invalid due date: {value!r} (expected YYYY-MM-DD)") from exc


def _clean_priority(value: Any) -> int:
    try:
        p = int(value)
    except (TypeError, ValueError) as exc:
        raise TodoError(f"invalid priority: {value!r}") from exc
    if not PRIORITY_MIN <= p <= PRIORITY_MAX:
        raise TodoError(f"priority must be {PRIORITY_MIN}–{PRIORITY_MAX}, got {p}")
    return p


def _clean_area(value: Any) -> str:
    area = str(value or "").strip()
    if area not in AREAS:
        raise TodoError(f"invalid area: {area!r} (one of {', '.join(AREAS)})")
    return area


def _clean_status(value: Any) -> str:
    if value not in STATUSES:
        raise TodoError(f"invalid status: {value!r} (one of {', '.join(STATUSES)})")
    return str(value)


def slugify(text: str) -> str:
    """ASCII slug for task ids (``Konto kündigen`` → ``konto-kuendigen``)."""
    text = text.lower()
    for src, dst in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:60] or "task"


def _unique_id(doc: dict[str, Any], title: str) -> str:
    existing = {t.get("id") for t in doc["tasks"]}
    base = slugify(title)
    candidate, n = base, 2
    while candidate in existing:
        candidate, n = f"{base}-{n}", n + 1
    return candidate


def _find(doc: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in doc["tasks"]:
        if task.get("id") == task_id:
            return task
    raise KeyError(task_id)


def _merge_subtasks(old: list[Any], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace the subtask list while keeping unknown keys of matching entries.

    Matching is by position — the UI always sends the full ordered list.
    """
    merged: list[dict[str, Any]] = []
    for i, sub in enumerate(new):
        title = str(sub.get("title", "")).strip()
        if not title:
            continue
        _check_sensitive(title)
        base = dict(old[i]) if i < len(old) and isinstance(old[i], dict) else {}
        base["title"] = title
        base["done"] = bool(sub.get("done", False))
        prio = sub.get("priority")
        base["priority"] = _clean_priority(prio if prio is not None else base.get("priority", 1))
        merged.append(base)
    return merged


def _apply_fields(task: dict[str, Any], fields: dict[str, Any]) -> None:
    """Apply known editable fields to ``task`` in place; others are left alone."""
    if "title" in fields:
        title = str(fields["title"]).strip()
        if not title:
            raise TodoError("title is required")
        task["title"] = title
    if "area" in fields:
        task["area"] = _clean_area(fields["area"])
    if "priority" in fields:
        task["priority"] = _clean_priority(fields["priority"])
    if "status" in fields:
        task["status"] = _clean_status(fields["status"])
    if "due" in fields:
        task["due"] = _clean_due(fields["due"])
    if "notes" in fields:
        task["notes"] = str(fields["notes"] or "")
    if "subtasks" in fields and fields["subtasks"] is not None:
        task["subtasks"] = _merge_subtasks(task.get("subtasks") or [], fields["subtasks"])
    # Only the fields being changed — pre-existing content never blocks an edit.
    _check_sensitive(*(task.get(k) for k in ("title", "notes", "area") if k in fields))


# --- Public operations -------------------------------------------------------
def create_task(fields: dict[str, Any]) -> dict[str, Any]:
    """Add a task; returns it (with its generated id)."""
    def op(doc: dict[str, Any]) -> dict[str, Any]:
        task: dict[str, Any] = {
            "id": "",
            "title": "",
            "area": DEFAULT_AREA,
            "priority": 2,
            "status": "open",
            "due": None,
            "notes": "",
            "subtasks": [],
        }
        _apply_fields(task, {"subtasks": [], **fields})
        task["id"] = _unique_id(doc, task["title"])
        doc["tasks"].append(task)
        logger.info("todos: created %s", task["id"])
        return task

    return _mutate(op)


def update_task(task_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Patch one task with the given fields; raises KeyError if the id is unknown."""
    def op(doc: dict[str, Any]) -> dict[str, Any]:
        task = _find(doc, task_id)
        _apply_fields(task, fields)
        logger.info("todos: updated %s (%s)", task_id, ", ".join(sorted(fields)))
        return task

    return _mutate(op)


def set_subtask_done(task_id: str, index: int, done: bool) -> dict[str, Any]:
    """Tick/untick one subtask by position."""
    def op(doc: dict[str, Any]) -> dict[str, Any]:
        task = _find(doc, task_id)
        subs = task.get("subtasks") or []
        if not 0 <= index < len(subs):
            raise TodoError(f"subtask index {index} out of range")
        subs[index]["done"] = bool(done)
        return task

    return _mutate(op)


def delete_task(task_id: str) -> None:
    """Remove a task entirely (the backup keeps the previous state)."""
    def op(doc: dict[str, Any]) -> None:
        task = _find(doc, task_id)
        doc["tasks"].remove(task)
        logger.info("todos: deleted %s", task_id)

    _mutate(op)
