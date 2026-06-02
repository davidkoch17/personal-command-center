"""Tasks API — wraps Task_Command_Center.md."""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    Task,
    TaskToggleRequest,
    TaskAddRequest,
    HardDate,
    ToggleByTextRequest,
)
from core import vault, markdown
from core.config import TASKS_FILE

router = APIRouter()

# Display order of the task sections (matched by case-insensitive heading prefix,
# so "Bigger items" finds "## Bigger items, no specific weekly deadline").
SECTIONS = ["This week", "Next week", "Bigger items", "This month", "Waiting for"]
# Sections whose bullets are dated previews (plain bullets, not checkbox tasks).
# Parsed with parse_section_lines so they still surface even without a checkbox.
PREVIEW_SECTIONS = {"Next week"}


@router.get("")
def list_tasks() -> dict[str, list[Task]]:
    """List bullets grouped by section.

    Checkbox sections (This week / Bigger items / This month / Waiting for) are
    parsed as toggleable tasks. Preview sections (Next week) keep their plain
    dated bullets and come back with ``is_task=False`` so the UI renders them
    read-only.
    """
    md = vault.read_md(TASKS_FILE)
    out: dict[str, list[Task]] = {}
    for section in SECTIONS:
        if section in PREVIEW_SECTIONS:
            bullets = markdown.parse_section_lines(md, section)
        else:
            bullets = markdown.parse_section_bullets(md, section)
        out[section] = [
            Task(
                text=b["text"],
                checked=b["checked"],
                section=section,
                line_index=b["line_index"],
                is_task=b.get("is_task", True),
            )
            for b in bullets
        ]
    return out


@router.get("/hard-dates")
def hard_dates() -> list[HardDate]:
    """Immovable real-world deadlines parsed from the task file's hard-dates block."""
    md = vault.read_md(TASKS_FILE)
    items = markdown.parse_hard_dates(md)
    return [
        HardDate(date=i["date"], label=i["label"], raw=i["raw"])
        for i in items
        if i["date"]
    ]


@router.post("/toggle")
def toggle_task(req: TaskToggleRequest) -> dict:
    """Toggle a specific task line by its 0-based line index."""
    md = vault.read_md(TASKS_FILE)
    if not md:
        raise HTTPException(status_code=404, detail="Task file not found or empty.")
    new_md, new_state = markdown.toggle_task(md, req.line_index)
    if new_md == md:
        raise HTTPException(status_code=400, detail="Line is not a toggleable task.")
    vault.write_md(TASKS_FILE, new_md)
    return {"ok": True, "new_state": new_state}


@router.post("/add")
def add_task(req: TaskAddRequest) -> dict:
    """Add a new unchecked task to the end of a section heading."""
    md = vault.read_md(TASKS_FILE)
    if not md:
        raise HTTPException(status_code=404, detail="Task file not found or empty.")
    new_md = markdown.add_task_to_section(md, req.section, req.text)
    if new_md == md:
        raise HTTPException(status_code=404, detail=f"Section '{req.section}' not found.")
    vault.write_md(TASKS_FILE, new_md)
    return {"ok": True}


# Checkbox bullet, e.g. "- [ ] text" / "  - [x] text" / "- [X] text".
_CHECKBOX_RE = re.compile(r"^\s*-\s*\[[ xX]\]")
_CHECKBOX_PREFIX_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s*")


@router.post("/toggle-by-text")
def toggle_by_text(req: ToggleByTextRequest) -> dict:
    """Find the first checkbox task fuzzily matching ``match`` and toggle it.

    Used by the Jarvis voice flow ("mark FFM apartment done"). Matching is
    case-insensitive and ignores markdown bold/italic markers, so a spoken
    phrase matches a bolded task. Returns ``{ok: False}`` (not an error) when
    nothing matches, so the assistant can speak a graceful miss.
    """
    md = vault.read_md(TASKS_FILE)
    if not md:
        raise HTTPException(status_code=404, detail="Task file not found or empty.")
    match_lower = req.match.strip().lower()
    if not match_lower:
        raise HTTPException(status_code=400, detail="Match text is required.")

    lines = md.split("\n")
    for i, line in enumerate(lines):
        if not _CHECKBOX_RE.match(line):
            continue
        text_part = _CHECKBOX_PREFIX_RE.sub("", line).lower()
        text_clean = re.sub(r"\*+", "", text_part)  # strip markdown bold/italic
        if match_lower in text_clean or text_clean.startswith(match_lower):
            new_md, new_state = markdown.toggle_task(md, i)
            vault.write_md(TASKS_FILE, new_md)
            return {"ok": True, "matched": text_part.strip(), "new_state": new_state}
    return {"ok": False, "error": f"No task matched '{req.match}'"}
