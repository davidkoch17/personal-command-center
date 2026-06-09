"""Week Planner endpoints (Phase 16).

Mounted under ``/api/planner``. The planner JSON stores only assignment; task
completion state lives in the source markdown (``/toggle`` writes back there).
"""
from fastapi import APIRouter
from pydantic import BaseModel
from modules.planner.week_planner import (
    load_week, save_week, aggregate_pool,
    carry_forward_from_last_week, toggle_task_completion,
    calendar_overlay_for_week, week_completion_stats, iso_week_key,
)
from modules.planner.ai_assistant import recommend_placements
from core import vault, markdown
from core.config import SYSTEM_PATH
from datetime import date


router = APIRouter()


@router.get("/pool")
def get_pool() -> dict:
    pool = aggregate_pool()
    today = date.today()
    current_iso = iso_week_key(today)
    # Mark which tasks are already assigned this week
    week_data = load_week(current_iso)
    assigned_ids = set()
    for day_key in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        for entry in week_data.get(day_key, []):
            assigned_ids.add(entry["task_id"])
    # Filter assigned out of pool view
    unassigned = [t for t in pool if t["id"] not in assigned_ids]
    # Add carry-forward badges
    carries = set(carry_forward_from_last_week(current_iso))
    for t in unassigned:
        t["is_carry_forward"] = t["id"] in carries
    # ``open_ids`` lets the frontend tell which *assigned* tasks are still open vs.
    # done — an assigned task whose id is absent here was checked off in its source.
    open_ids = [t["id"] for t in pool]
    return {
        "pool": unassigned,
        "open_ids": open_ids,
        "total_open": len(pool),
        "assigned_count": len(assigned_ids),
    }


@router.get("/week/{iso_week}")
def get_week(iso_week: str):
    return {
        "week": load_week(iso_week),
        "calendar": calendar_overlay_for_week(iso_week),
        "stats": week_completion_stats(iso_week),
    }


class SaveWeekRequest(BaseModel):
    week: dict


@router.post("/week/{iso_week}")
def post_week(iso_week: str, req: SaveWeekRequest):
    save_week(iso_week, req.week)
    return {"ok": True}


class ToggleRequest(BaseModel):
    task_id: str


@router.post("/toggle")
def toggle(req: ToggleRequest):
    return toggle_task_completion(req.task_id)


@router.post("/ai-recommend/{iso_week}")
def ai_recommend(iso_week: str):
    pool = aggregate_pool()
    week_data = load_week(iso_week)
    calendar = calendar_overlay_for_week(iso_week)
    # Hard dates from Task_Command_Center.md so placement respects deadlines.
    tasks_md = vault.read_md(SYSTEM_PATH / "Task_Command_Center.md")
    hard_dates = [
        {"date": d["date"].isoformat() if d.get("date") else None, "label": d["label"]}
        for d in markdown.parse_hard_dates(tasks_md)
    ]
    return recommend_placements(pool, week_data, calendar, hard_dates)
