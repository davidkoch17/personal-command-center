"""Week Planner — drag-and-drop weekly task assignment.

Storage: one JSON file per ISO week at ``99_System/Week_Planner/YYYY-Www.json``.
The JSON stores only ASSIGNMENT (which task_id lands on which day); task *state*
(open/done) always lives in the source markdown, so toggling completion in the
planner writes straight back to the source file.

Task identity is a stable hash of ``source_path + task_text`` — it survives
reordering and re-aggregation but intentionally breaks on a text edit (treated
as a new task, which is acceptable).
"""
from datetime import date, timedelta, datetime
from pathlib import Path
import json
import hashlib
import re

from core.config import VAULT_PATH, SYSTEM_PATH
from core import vault, markdown


PLANNER_DIR = SYSTEM_PATH / "Week_Planner"

_DAY_KEYS = [
    "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday",
]


def iso_week_key(d: date) -> str:
    """YYYY-Www format for given date."""
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def week_dates(iso_key: str) -> list[date]:
    """Returns 7 dates Mon..Sun for the given ISO week."""
    year, week = iso_key.split("-W")
    monday = date.fromisocalendar(int(year), int(week), 1)
    return [monday + timedelta(days=i) for i in range(7)]


def task_id(source: str, text: str) -> str:
    """Stable ID from source path + task text."""
    raw = f"{source}|{text.strip().lower()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def planner_file_path(iso_key: str) -> Path:
    return PLANNER_DIR / f"{iso_key}.json"


def load_week(iso_key: str) -> dict:
    """Load a week's assignments. Returns empty structure if file doesn't exist."""
    PLANNER_DIR.mkdir(parents=True, exist_ok=True)
    p = planner_file_path(iso_key)
    if not p.exists():
        return {
            "iso_week": iso_key,
            "monday": [], "tuesday": [], "wednesday": [],
            "thursday": [], "friday": [], "saturday": [], "sunday": [],
            "last_modified": None,
        }
    return json.loads(p.read_text(encoding="utf-8"))


def save_week(iso_key: str, week_data: dict) -> Path:
    """Save week assignments."""
    PLANNER_DIR.mkdir(parents=True, exist_ok=True)
    week_data["iso_week"] = iso_key
    week_data["last_modified"] = datetime.now().isoformat()
    p = planner_file_path(iso_key)
    if p.exists():
        # Backup before overwrite
        backup = p.with_suffix(".json.bak")
        backup.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    p.write_text(json.dumps(week_data, indent=2), encoding="utf-8")
    return p


def aggregate_pool() -> list[dict]:
    """Aggregate all open tasks from sources. Returns task records with stable IDs."""
    pool = []

    # Source 1: Task_Command_Center.md
    tasks_md = vault.read_md(SYSTEM_PATH / "Task_Command_Center.md")
    tcc_path = str(SYSTEM_PATH / "Task_Command_Center.md")
    sections = ["This week", "Next week", "Bigger items", "Waiting for"]
    for section in sections:
        bullets = markdown.parse_section_bullets(tasks_md, section) if hasattr(markdown, "parse_section_bullets") else []
        for b in bullets:
            if not b.get("checked"):
                pool.append({
                    "id": task_id(tcc_path, b["text"]),
                    "text": b["text"],
                    "source_path": tcc_path,
                    "source_label": f"Tasks / {section}",
                    "source_section": section,
                    "line_index": b.get("line_index"),
                    "is_completed": False,
                })

    # Source 2: Project READMEs — ## Next Steps sections
    from core.config import PROJECTS_PATH
    for d in PROJECTS_PATH.iterdir():
        if not d.is_dir() or d.name.startswith(("_", ".", "98")):
            continue
        readme = d / "README.md"
        if not readme.exists():
            continue
        readme_md = readme.read_text(encoding="utf-8")
        next_steps = markdown.parse_section_bullets(readme_md, "Next Steps") if hasattr(markdown, "parse_section_bullets") else []
        for b in next_steps:
            if not b.get("checked"):
                pool.append({
                    "id": task_id(str(readme), b["text"]),
                    "text": b["text"],
                    "source_path": str(readme),
                    "source_label": d.name,
                    "source_section": "Next Steps",
                    "line_index": b.get("line_index"),
                    "is_completed": False,
                })

    return pool


def carry_forward_from_last_week(current_iso_key: str) -> list[str]:
    """If transitioning to a new week on Monday, return task IDs that
    were assigned to LAST week's days but uncompleted, so they can resurface in pool.
    """
    today = date.today()
    year, week = current_iso_key.split("-W")
    last_monday = date.fromisocalendar(int(year), int(week), 1) - timedelta(days=7)
    last_iso = iso_week_key(last_monday)
    last_week_data = load_week(last_iso)

    pool_ids = {t["id"] for t in aggregate_pool()}  # currently open tasks

    carry = []
    for day_key in _DAY_KEYS:
        for entry in last_week_data.get(day_key, []):
            if entry["task_id"] in pool_ids:
                # Still open → carry forward
                carry.append(entry["task_id"])
    return carry


def toggle_task_completion(task_id_to_toggle: str) -> dict:
    """Find task by ID across all sources, toggle its checkbox, write back."""
    # Iterate sources, find matching task by ID
    for task in aggregate_pool():
        if task["id"] == task_id_to_toggle:
            src = Path(task["source_path"])
            md = vault.read_md(src)
            new_md, new_state = markdown.toggle_task(md, task["line_index"])
            vault.write_md(src, new_md)
            return {"ok": True, "new_state": new_state, "task": task}
    return {"ok": False, "error": f"Task {task_id_to_toggle} not found"}


def calendar_overlay_for_week(iso_key: str) -> dict:
    """Return calendar events per day of the given week."""
    try:
        from modules.integrations.calendar_ical import fetch_events
        events = fetch_events(days_ahead=30)
        dates = week_dates(iso_key)
        out = {day_key: [] for day_key in _DAY_KEYS}
        day_keys = _DAY_KEYS
        for ev in events:
            ev_date = ev["start"].date() if hasattr(ev["start"], "date") else None
            if ev_date and ev_date in dates:
                day_key = day_keys[dates.index(ev_date)]
                out[day_key].append({
                    "title": ev["title"][:40],
                    "start": ev["start"].strftime("%H:%M") if hasattr(ev["start"], "strftime") else "",
                    "is_all_day": False,
                })
        return out
    except Exception:
        return {}


def week_completion_stats(iso_key: str) -> dict:
    """Total assigned tasks + how many done, per week."""
    week_data = load_week(iso_key)
    total = 0
    done = 0
    done_tasks = []
    pool = {t["id"]: t for t in aggregate_pool()}

    # Also build a "completed task IDs" set by hash matching against now-completed source bullets
    # Simpler: iterate all assignments, check source's current state

    for day_key in _DAY_KEYS:
        for entry in week_data.get(day_key, []):
            total += 1
            tid = entry["task_id"]
            # If NOT in current pool (which contains only OPEN tasks), it's done
            if tid not in pool:
                done += 1
                done_tasks.append({"id": tid, "day": day_key, "text": entry.get("text_cache", "(text not cached)")})

    return {
        "total": total,
        "done": done,
        "percentage": round(done / total * 100, 1) if total > 0 else 0,
        "done_tasks": done_tasks,
    }
