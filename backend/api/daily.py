"""Daily Priorities endpoints — morning suggestions + the per-day curated list.

Backs the ``DailyPrioritiesPanel`` on Home. ``/today`` reads the persisted
``99_System/Daily_Todos/YYYY-MM-DD.md`` file; ``/today/generate`` asks Claude
for fresh suggestions (slow, ~60-120s); the rest mutate today's file.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from modules.agents.skills.daily_priorities import (
    add_to_daily,
    create_daily_file,
    read_today,
    suggest_priorities,
    toggle_daily_item,
)

router = APIRouter()


@router.get("/today")
def get_today() -> dict:
    """Return today's curated list (or ``exists: false`` if not generated yet)."""
    return read_today()


@router.post("/today/generate")
def generate_today() -> dict:
    """Generate today's priority suggestions (manual refresh or first load)."""
    return suggest_priorities()


class AcceptRequest(BaseModel):
    priorities: list[dict]


@router.post("/today/accept")
def accept_priorities(req: AcceptRequest) -> dict:
    """Commit accepted priorities to today's file."""
    create_daily_file(priorities=req.priorities)
    return {"ok": True}


class AddItemRequest(BaseModel):
    text: str


@router.post("/today/add")
def add_item(req: AddItemRequest) -> dict:
    add_to_daily(req.text)
    return {"ok": True}


class ToggleRequest(BaseModel):
    text: str


@router.post("/today/toggle")
def toggle_item(req: ToggleRequest) -> dict:
    toggle_daily_item(req.text)
    return {"ok": True}
