"""Inbox API — triage 0_Inbox/ items (list, capture, move/archive/delete/convert)."""
from __future__ import annotations

import shutil
from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.models.schemas import InboxCaptureRequest, InboxActionRequest
from core import vault, markdown
from core.config import INBOX_PATH, VAULT_PATH, TASKS_FILE
from modules.projects import workspace

router = APIRouter()

ARCHIVE_DIR = VAULT_PATH / "9_Archive" / "Inbox_Archive"


def _inbox_path(filename: str):
    """Resolve a filename to an inbox file, blocking path traversal."""
    path = (INBOX_PATH / filename).resolve()
    if path.parent != INBOX_PATH.resolve() or not path.exists():
        raise HTTPException(status_code=404, detail=f"Inbox item not found: {filename}")
    return path


@router.get("")
def list_inbox() -> list[dict]:
    """List top-level markdown items in the inbox, newest first, with previews."""
    out = []
    for path in vault.list_files(INBOX_PATH):
        content = vault.read_md(path)
        preview = content[:500] + ("…" if len(content) > 500 else "")
        out.append({
            "filename": path.name,
            "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            "preview": preview,
        })
    return out


@router.post("/capture")
def capture(req: InboxCaptureRequest) -> dict:
    """Quick-capture a snippet as a new timestamped inbox markdown file."""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Capture content is empty.")
    path = vault.append_to_inbox(req.content, req.source)
    return {"ok": True, "filename": path.name, "path": str(path)}


@router.post("/{filename}/action")
def action(filename: str, req: InboxActionRequest) -> dict:
    """Move to a project, archive, delete, or convert an inbox item to a task."""
    path = _inbox_path(filename)

    if req.action == "delete":
        path.unlink()
        return {"ok": True, "action": "delete"}

    if req.action == "archive":
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(ARCHIVE_DIR / path.name))
        return {"ok": True, "action": "archive"}

    if req.action == "move":
        if not req.project_id:
            raise HTTPException(status_code=400, detail="project_id is required for move.")
        try:
            dest_dir = workspace.project_root(req.project_id) / "0_Inbox"
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(dest_dir / path.name))
        return {"ok": True, "action": "move", "project_id": req.project_id}

    if req.action == "convert_to_task":
        section = req.section or "This week"
        title = (req.title or path.stem).strip()
        md = vault.read_md(TASKS_FILE)
        new_md = markdown.add_task_to_section(md, section, title)
        if new_md == md:
            raise HTTPException(status_code=404, detail=f"Section '{section}' not found in task file.")
        vault.write_md(TASKS_FILE, new_md)
        path.unlink()
        return {"ok": True, "action": "convert_to_task", "section": section}

    raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")
