"""To-dos pillar API — wraps modules.todos.store (the shared ``todos.json``)."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config import TODOS_FILE, get_logger
from modules.todos import store

logger = get_logger(__name__)

router = APIRouter()


class SubtaskIn(BaseModel):
    title: str
    done: bool = False
    priority: int = 1


class TodoFields(BaseModel):
    """Editable task fields. Omitted fields are left untouched on update."""
    title: Optional[str] = None
    area: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    due: Optional[str] = None
    notes: Optional[str] = None
    subtasks: Optional[list[SubtaskIn]] = None


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
    return {**doc, "path": str(TODOS_FILE), "statuses": list(store.STATUSES)}


@router.post("")
def create_todo(body: TodoFields) -> dict:
    if not body.title:
        raise HTTPException(status_code=422, detail="title is required")
    return _run(store.create_task, _fields(body))


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
