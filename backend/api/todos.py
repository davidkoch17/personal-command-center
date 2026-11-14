"""To-dos pillar API — wraps modules.todos.store (the shared ``todos.json``)."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config import TODOS_FILE, get_logger
from modules.todos import reminders, screenshot, store

logger = get_logger(__name__)

router = APIRouter()


class SubtaskIn(BaseModel):
    title: str
    done: bool = False
    priority: Optional[int] = None  # None → keep existing / default 1


class TodoFields(BaseModel):
    """Editable task fields. Omitted fields are left untouched on update."""
    title: Optional[str] = None
    area: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    due: Optional[str] = None
    notes: Optional[str] = None
    subtasks: Optional[list[SubtaskIn]] = None
    session: Optional[bool] = None  # on the "working session" list


class TodoBatch(BaseModel):
    tasks: list[TodoFields]


class ImageImport(BaseModel):
    image_base64: str  # raw base64, no data: prefix
    mime: str = "image/png"


class SubtaskToggle(BaseModel):
    done: bool


def _fields(body: TodoFields) -> dict[str, Any]:
    return body.model_dump(exclude_unset=True)


def _run(fn, *args):
    try:
        return fn(*args)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"task not found: {exc.args[0]}") from exc
    except store.TodoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("")
def get_todos() -> dict:
    """Full document (fresh from disk) plus the file path for the UI footer."""
    doc = _run(store.load)
    return {
        **doc,
        "path": str(TODOS_FILE),
        "statuses": list(store.STATUSES),
        "areas": list(store.AREAS),
    }


@router.post("")
def create_todo(body: TodoFields) -> dict:
    if not body.title:
        raise HTTPException(status_code=422, detail="title is required")
    return _run(store.create_task, _fields(body))


@router.post("/batch")
def create_todos(body: TodoBatch) -> dict:
    """Create several tasks in one write (all-or-nothing)."""
    items = [t.model_dump(exclude_unset=True) for t in body.tasks]
    return {"created": _run(store.create_tasks, items)}


@router.post("/import-image")
def import_image(body: ImageImport) -> dict:
    """Read a pasted screenshot with Claude and return PROPOSED tasks.

    Nothing is written; the UI lets David review, then calls /batch.
    """
    try:
        return {"proposals": screenshot.extract_todos(body.image_base64, body.mime)}
    except store.TodoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:  # claude -p failure (e.g. login expired)
        logger.warning("screenshot import failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/reminders")
def reminder_status() -> dict:
    """Push-reminder config + what tonight's digest would contain."""
    groups = reminders.build_digest(store.load()["tasks"])
    preview = reminders.format_digest(groups)
    return {
        **reminders.status(),
        "preview": {"title": preview[0], "body": preview[1]} if preview else None,
    }


@router.post("/reminders/test")
def reminder_test() -> dict:
    """Send the digest now (or a test message if nothing is due)."""
    if not reminders.configured():
        raise HTTPException(status_code=409, detail="NTFY_TOPIC is not set in .env")
    try:
        return reminders.send_digest(force=True)
    except Exception as exc:  # noqa: BLE001 - surface network errors to the UI
        raise HTTPException(status_code=502, detail=f"push failed: {exc}") from exc


@router.patch("/{task_id}")
def update_todo(task_id: str, body: TodoFields) -> dict:
    return _run(store.update_task, task_id, _fields(body))


@router.put("/{task_id}/subtasks/{index}")
def toggle_subtask(task_id: str, index: int, body: SubtaskToggle) -> dict:
    return _run(store.set_subtask_done, task_id, index, body.done)


@router.delete("/{task_id}")
def delete_todo(task_id: str) -> dict:
    _run(store.delete_task, task_id)
    return {"deleted": task_id}
