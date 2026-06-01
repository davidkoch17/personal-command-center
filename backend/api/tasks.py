"""Tasks API — wraps Task_Command_Center.md."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import Task, TaskToggleRequest, TaskAddRequest
from core import vault, markdown
from core.config import TASKS_FILE

router = APIRouter()

SECTIONS = ["Today", "This weekend", "This week", "This month", "Waiting for"]


@router.get("")
def list_tasks() -> dict[str, list[Task]]:
    """List checkbox bullets grouped by section."""
    md = vault.read_md(TASKS_FILE)
    out: dict[str, list[Task]] = {}
    for section in SECTIONS:
        bullets = markdown.parse_section_bullets(md, section)
        out[section] = [
            Task(text=b["text"], checked=b["checked"], section=section, line_index=b["line_index"])
            for b in bullets
        ]
    return out


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
