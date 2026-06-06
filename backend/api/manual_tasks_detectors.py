"""Manual-task detectors — "Awaiting your input" on Home (Manual_Tasks_Card_Spec.md).

Each detector is a zero-arg function returning ``Optional[dict]`` (a task per
the endpoint contract) — None means nothing is awaiting David for that source.
The ``/api/home/manual-tasks`` endpoint iterates ``DETECTORS`` and collects
non-None results, so adding a new manual-fill requirement = adding ONE function
here and appending it to the list. The Home card auto-picks it up.

The list auto-resolves: a detector returns None as soon as its file is filled
correctly — no manual marking-done anywhere.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Callable, Optional

from core.config import SYSTEM_PATH, get_logger

logger = get_logger(__name__)

READING_STATUS_FILE = SYSTEM_PATH / "Reading_Status.md"
WEEKLY_REVIEWS_DIR = SYSTEM_PATH / "Weekly_Reviews"

# Markers in the Book: line that mean "template not filled in yet".
_PLACEHOLDER_MARKERS = ("[TBD", "[FILL")


def _detect_reading_status() -> Optional[dict]:
    """Reading_Status.md's ``## Current`` block still has placeholder markers.

    Fires when the file is missing entirely, or the ``Book:`` line is empty /
    contains ``[TBD`` / ``[FILL`` — i.e. the Brain/System card has no real
    reading data to show.
    """
    task = {
        "id": "reading_status",
        "title": "Fill in your current book",
        "what": "Book title + author, start date, last read date, chapter progress",
        "file_path": "99_System/Reading_Status.md",
        "section": "## Current",
        "why": "Brain/System card on Home uses this for reading status",
        "estimated_time": "2 min",
        "priority": "low",
    }
    if not READING_STATUS_FILE.exists():
        task["what"] = "Create the file from the template, then fill the ## Current block"
        task["section"] = "(file missing — create it)"
        return task
    book = ""
    in_current = False
    for line in READING_STATUS_FILE.read_text(encoding="utf-8").split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith("## "):
            if in_current:
                break
            in_current = stripped.lower() == "## current"
            continue
        if in_current:
            body = stripped.lstrip("- ").strip()
            if body.startswith("Book:"):
                book = body[len("Book:"):].strip()
                break
    if not book or any(m in book for m in _PLACEHOLDER_MARKERS):
        return task
    return None


def _current_week_sunday(today: date | None = None) -> date:
    """The Sunday of the current Mo–Su week (today if today IS Sunday)."""
    today = today or date.today()
    return today + timedelta(days=(6 - today.weekday()) % 7)


def _detect_weekly_review_missing() -> Optional[dict]:
    """No review file exists for the current week's Sunday.

    Accepts either filename convention from Weekly_Reviews/README.md: the
    Sunday-dated ``YYYY-MM-DD.md`` or the ISO-week ``YYYY-WNN.md`` for the same
    week. When several weeks have gone unreviewed, one task is returned with an
    "(N weeks overdue)" title rather than one task per missed Sunday.
    """
    sunday = _current_week_sunday()
    iso_year, iso_week, _ = sunday.isocalendar()
    candidates = (
        WEEKLY_REVIEWS_DIR / f"{sunday.isoformat()}.md",
        WEEKLY_REVIEWS_DIR / f"{iso_year}-W{iso_week:02d}.md",
    )
    if any(p.exists() for p in candidates):
        return None

    # How far behind: weeks since the most recent review on file (any week).
    title = f"Write Weekly Review for week of {sunday.isoformat()}"
    last = _latest_review_date()
    if last is not None:
        weeks_missing = (sunday - last).days // 7
        if weeks_missing > 1:
            title = f"Write Weekly Review ({weeks_missing} weeks overdue)"
    return {
        "id": f"weekly_review_{sunday.isoformat()}",
        "title": title,
        "what": "Sunday-evening retrospective + 3 priorities for next week",
        "file_path": f"99_System/Weekly_Reviews/{sunday.isoformat()}.md",
        "section": "(create new file using template in README.md)",
        "why": "Brain/System card shows days since last review + countdown",
        "estimated_time": "15 min",
        "priority": "medium",
        # Seeds the in-app editor, since the target file doesn't exist yet.
        "template": _weekly_review_template(sunday),
    }


def _weekly_review_template(sunday: date) -> Optional[str]:
    """The README's fenced template, with the Sunday date substituted in."""
    try:
        text = (WEEKLY_REVIEWS_DIR / "README.md").read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"```markdown\r?\n(.*?)```", text, re.DOTALL)
    if m is None:
        return None
    return m.group(1).replace("YYYY-MM-DD", sunday.isoformat())


def _latest_review_date() -> Optional[date]:
    """Most recent review date on file, by filename (both naming conventions)."""
    # Local import: home.py owns the filename-date parsing used by the
    # Brain/System card; reuse it so the two features can't drift apart.
    from backend.api.home import _review_file_date

    if not WEEKLY_REVIEWS_DIR.exists():
        return None
    dates = [_review_file_date(p) for p in WEEKLY_REVIEWS_DIR.glob("*.md")]
    dates = [d for d in dates if d is not None]
    return max(dates) if dates else None


# --- Deferred detector slots (Manual_Tasks_Card_Spec.md) ----------------------
# Build these when their respective pages/projects exist; each follows the same
# zero-arg -> Optional[dict] contract and just needs appending to DETECTORS.

# def _detect_money_third_insurance() -> Optional[dict]:
#     """TODO (after Money page enhancement, Item #7): fire while the third
#     insurance (likely Haftpflicht or Unfall — David confirms in brainstorm)
#     has no file/decision under 2_Personal/04_Versicherungen/."""

# def _detect_immos_flow_b_readme() -> Optional[dict]:
#     """TODO (after Immos Flow B setup): fire while
#     1_Projects/06_Immos/README.md is missing or has no real content
#     (milestones / next steps), per the 2026-06-05 Flow B decision."""

# def _detect_career_evercore_checklist() -> Optional[dict]:
#     """TODO (after Career page build, Item #6): fire while the Evercore prep
#     file (3_Career/01_Evercore/) is missing or its checklist is untouched."""

# def _detect_brand_inspo_dump() -> Optional[dict]:
#     """TODO (after Brand page population, Item #5): fire while
#     1_Projects/05_Personal_Brand/02_Inspirations/ is empty — the edit
#     pipeline needs at least a first inspo dump to work from."""

# def _detect_project_readmes_missing_next_step() -> Optional[dict]:
#     """TODO (generic project hygiene): fire when any ACTIVE project README
#     has no open next step — one aggregated task listing the offenders."""


# Endpoint iterates these in order; ordering = display order on Home.
DETECTORS: list[Callable[[], Optional[dict]]] = [
    _detect_reading_status,
    _detect_weekly_review_missing,
]


def collect_manual_tasks() -> dict:
    """Run every detector (each fail-safe) and assemble the endpoint payload."""
    tasks: list[dict] = []
    for detector in DETECTORS:
        try:
            task = detector()
        except Exception:  # noqa: BLE001 - one broken detector must not hide the rest
            logger.warning("manual-tasks detector %s failed", detector.__name__, exc_info=True)
            continue
        if task is not None:
            tasks.append(task)
    return {"tasks": tasks, "all_clear": not tasks}
