"""Home API — data for the redesigned Home tab (Item #4, Home_Redesign_Spec.md).

Four read-only aggregation endpoints, one per Home zone widget:
- ``/focus-areas``     NOW zone: the 7 locked focus area cards
- ``/watchlist-signals`` STATE: headlines from the latest Market Brief
- ``/notgroschen``     STATE: emergency-fund progress (phase 1) / depot funding (phase 2)
- ``/tasks-summary``   GROUND: open-task counts + top items

Everything is best-effort: a missing vault file degrades the affected card,
never the whole endpoint.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from fastapi import APIRouter

from core import markdown, vault
from core.config import (
    EVERCORE_START_DATE,
    INBOX_PATH,
    MARKET_BRIEFS_DIR,
    PROJECT_INDEX_FILE,
    READING_LIST_PATH,
    SYSTEM_PATH,
    TASKS_FILE,
    get_logger,
)
from modules.projects import workspace

router = APIRouter()
logger = get_logger(__name__)

NOTGROSCHEN_TARGET_EUR = 4_000.0

# Project-status emoji key -> focus-card status dot.
_PROJECT_DOT = {
    "ON TRACK": "green",
    "NEEDS ATTENTION": "yellow",
    "AT RISK": "red",
    "DONE": "green",
}


def _days_until(target: date) -> int:
    return (target - date.today()).days


def _relative(d: date | None) -> str | None:
    """Compact countdown: "today" / "in 3d" / "5d ago"."""
    if d is None:
        return None
    delta = _days_until(d)
    if delta == 0:
        return "today"
    return f"in {delta}d" if delta > 0 else f"{-delta}d ago"


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s).strip())
    except (ValueError, AttributeError):
        return None


# --- Focus area assemblers ----------------------------------------------------
def _career_card() -> dict:
    start = _parse_date(EVERCORE_START_DATE)
    days = _days_until(start) if start else None
    next_action = "structured Evercore prep"
    status = "green"
    try:
        from modules.career import tracker

        onboarding = tracker.read_onboarding()
        open_items = [i for i in onboarding if not i["checked"]]
        if open_items:
            next_action = open_items[0]["text"]
        done = len(onboarding) - len(open_items)
        if days is not None and days <= 21 and onboarding and done / len(onboarding) < 0.5:
            status = "yellow"
    except Exception:  # noqa: BLE001 - card degrades, endpoint survives
        logger.debug("focus: onboarding unavailable", exc_info=True)
    return {
        "key": "career",
        "title": "Career — Evercore",
        "status": status,
        "next_action": next_action,
        "time_indicator": f"{days}d to start" if days is not None and days >= 0 else "started",
        "target": "/career",
        "new_tab": False,
    }


def _wealth_card() -> dict:
    status = "green"
    next_action = "log monthly wealth check"
    time_indicator = None
    try:
        from modules.finance.loader import net_worth

        nw = net_worth()
        if not nw.empty and "Total Net Worth (€)" in nw.columns:
            totals = nw["Total Net Worth (€)"].dropna()
            if len(totals) >= 2:
                delta = float(totals.iloc[-1]) - float(totals.iloc[-2])
                sign = "+" if delta >= 0 else "−"
                next_action = f"net worth {sign}€{abs(delta):,.0f} vs last month"
                if delta < 0:
                    status = "yellow"
    except Exception:  # noqa: BLE001
        logger.debug("focus: net worth unavailable", exc_info=True)
    # Monthly Wealth Check cadence: due on the 1st of each month (skill build is
    # item #77 — until it exists this is a calendar nudge, not a run status).
    today = date.today()
    next_first = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    time_indicator = f"check {_relative(next_first)}"
    return {
        "key": "wealth",
        "title": "Wealth / Net Worth",
        "status": status,
        "next_action": next_action,
        "time_indicator": time_indicator,
        "target": "/money",
        "new_tab": False,
    }


def _project_card(
    key: str, title: str, project_id: str, target: str, new_tab: bool
) -> dict:
    status, next_action, time_indicator = "yellow", f"set up {project_id} project README", None
    try:
        projects = {p["id"]: p for p in markdown.parse_projects(vault.read_md(PROJECT_INDEX_FILE))}
        proj = projects.get(project_id)
        if proj:
            label, _ = markdown.status_display(proj)
            status = _PROJECT_DOT.get(label, "yellow")
            next_action = proj.get("next_step") or "(no next step)"
            try:
                root = workspace.project_root(project_id)
                readme = vault.read_md(root / "README.md")
                steps = [s for s in workspace.parse_next_steps(readme) if not s["checked"]]
                if steps:
                    next_action = steps[0]["text"]
                milestones = workspace.parse_milestones(readme)
                dated = sorted(
                    [(m, _parse_date(m.get("date"))) for m in milestones if _parse_date(m.get("date"))],
                    key=lambda x: x[1],
                )
                upcoming = [(m, d) for m, d in dated if d >= date.today()]
                if upcoming:
                    time_indicator = _relative(upcoming[0][1])
            except FileNotFoundError:
                pass
    except Exception:  # noqa: BLE001
        logger.debug("focus: project %s unavailable", project_id, exc_info=True)
    return {
        "key": key,
        "title": title,
        "status": status,
        "next_action": next_action,
        "time_indicator": time_indicator,
        "target": target,
        "new_tab": new_tab,
    }


def _brain_card() -> dict:
    next_action = "no active book"
    try:
        buckets = markdown.parse_reading_list(vault.read_md(READING_LIST_PATH))
        reading = buckets.get("reading_now") or []
        if reading:
            # Strip markdown emphasis for a clean one-liner.
            next_action = "reading: " + re.sub(r"[*_\[\]]", "", reading[0])[:48]
    except Exception:  # noqa: BLE001
        logger.debug("focus: reading list unavailable", exc_info=True)
    pending = 0
    try:
        pending = len(vault.list_files(INBOX_PATH))
    except Exception:  # noqa: BLE001
        logger.debug("focus: inbox unavailable", exc_info=True)
    # Weekly review anchor: Sunday evening (same trigger as the weekly briefing).
    days_to_sunday = (6 - date.today().weekday()) % 7
    review = "review today" if days_to_sunday == 0 else f"review in {days_to_sunday}d"
    return {
        "key": "brain",
        "title": "Brain / System",
        "status": "yellow" if pending > 20 else "green",
        "next_action": next_action,
        "time_indicator": f"{pending} inbox · {review}",
        "target": "/settings",
        "new_tab": False,
    }


@router.get("/focus-areas")
def focus_areas() -> dict:
    """The 7 locked focus area cards (Home_Redesign_Spec.md §1a), in locked order."""
    cards = [
        _career_card(),
        _wealth_card(),
        _project_card("ulli", "Project Ulli", "03", "/workspace/project/03", True),
        _project_card("kande", "Project K&E", "02", "/workspace/project/02", True),
        _project_card("brand", "Project Brand", "05", "/brand", False),
        _project_card("immos", "Immos (personal)", "06", "/workspace/project/06", True),
        _brain_card(),
    ]
    return {"cards": cards}


# --- Watchlist signals ---------------------------------------------------------
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def _clean_bullet(text: str) -> str:
    text = _MD_LINK_RE.sub(lambda m: m.group(1) if m.group(1) != "source" else "", text)
    text = _BOLD_RE.sub(r"\1", text)
    text = re.sub(r"\[(computed|filing|verify)\]", "", text)
    return re.sub(r"\s+", " ", text).strip(" .—-")


@router.get("/watchlist-signals")
def watchlist_signals() -> dict:
    """Headline bullets from the latest Market Brief (TL;DR section, top 5)."""
    briefs = sorted(MARKET_BRIEFS_DIR.glob("*.md"), reverse=True) if MARKET_BRIEFS_DIR.exists() else []
    if not briefs:
        return {"brief_date": None, "age_days": None, "signals": []}
    latest = briefs[0]
    brief_date = _parse_date(latest.stem[:10])
    signals: list[str] = []
    try:
        in_tldr = False
        for line in latest.read_text(encoding="utf-8").split("\n"):
            if line.startswith("## "):
                if in_tldr:
                    break
                in_tldr = "tl;dr" in line.lower()
                continue
            if in_tldr and line.lstrip().startswith("- "):
                cleaned = _clean_bullet(line.lstrip()[2:])
                if cleaned:
                    signals.append(cleaned[:160])
    except OSError:
        logger.warning("watchlist signals: could not read %s", latest, exc_info=True)
    return {
        "brief_date": brief_date.isoformat() if brief_date else latest.stem,
        "age_days": _days_until(brief_date) * -1 if brief_date else None,
        "signals": signals[:5],
    }


# --- Notgroschen ----------------------------------------------------------------
@router.get("/notgroschen")
def notgroschen() -> dict:
    """Emergency-fund progress (Home_Redesign_Spec.md §2d).

    Phase 1 (cash < €4,000): progress toward the €4,000 Tagesgeld target.
    Phase 2 (cash >= €4,000): switch to depot funding — cumulative invested
    capital (cost basis of current holdings).
    """
    from modules.finance import money, positions

    cash = money.current_cash_balance()
    phase = 2 if cash is not None and cash >= NOTGROSCHEN_TARGET_EUR else 1
    depot_invested = None
    if phase == 2:
        try:
            depot_invested = round(
                sum(positions.cost_basis(t)[1] for t in positions.current_holdings()), 2
            )
        except Exception:  # noqa: BLE001
            logger.debug("notgroschen: depot basis unavailable", exc_info=True)
    pct = (
        max(0.0, min(1.0, cash / NOTGROSCHEN_TARGET_EUR))
        if cash is not None
        else None
    )
    return {
        "phase": phase,
        "cash_balance": cash,
        "target": NOTGROSCHEN_TARGET_EUR,
        "pct": pct,
        "depot_invested": depot_invested,
    }


# --- Brain/System card (Brain_System_Card_Spec.md) --------------------------------
ACTIVE_BACKLOG_FILE = SYSTEM_PATH / "Active_Backlog.md"
READING_STATUS_FILE = SYSTEM_PATH / "Reading_Status.md"
WEEKLY_REVIEWS_DIR = SYSTEM_PATH / "Weekly_Reviews"

_UPGRADE_BULLET_RE = re.compile(r"^-\s+([A-Z]+\d+[a-z]?)\s+(.+)$")
_REVIEW_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_REVIEW_WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$", re.IGNORECASE)


def _parse_pending_upgrades() -> dict | None:
    """Knowledge-layer vault upgrades from Active_Backlog.md's PARK section.

    Bullets look like ``- D1 Backlink conventions + backfill`` — id then title.
    Returns ``{count, top: [first 2]}``, or None if the file/section can't be
    parsed (frontend renders the count as "?").
    """
    try:
        text = ACTIVE_BACKLOG_FILE.read_text(encoding="utf-8")
    except OSError:
        logger.debug("brain-system: Active_Backlog.md unreadable", exc_info=True)
        return None
    in_park = False
    in_knowledge = False
    items: list[dict] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not in_park:
            if stripped.startswith("### PARK"):
                in_park = True
            continue
        if stripped.startswith("### "):  # next ### section ends PARK
            break
        if not in_knowledge:
            if stripped.lower().startswith("**knowledge layer"):
                in_knowledge = True
            continue
        # Inside the Knowledge-layer list: bullets until the next bold
        # subsection header (e.g. "**Separate projects ...**") or a heading.
        if stripped.startswith("**") or stripped.startswith("#"):
            break
        m = _UPGRADE_BULLET_RE.match(stripped)
        if m:
            items.append({"id": m.group(1), "title": m.group(2).strip()})
    if not in_knowledge:
        return None
    return {"count": len(items), "top": items[:2]}


def _parse_reading_status() -> dict | None:
    """The ``## Current`` block of Reading_Status.md, parsed by line prefix.

    Returns None when the file is missing or the block is empty / still the
    unfilled template (placeholder book line) — frontend says "no book tracked".
    """
    try:
        text = READING_STATUS_FILE.read_text(encoding="utf-8")
    except OSError:
        return None
    fields: dict[str, str] = {}
    in_current = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith("## "):
            if in_current:
                break
            in_current = stripped.lower() == "## current"
            continue
        if not in_current:
            continue
        body = stripped.lstrip("- ").strip()
        for prefix, key in (
            ("Book:", "current_book"),
            ("Started:", "started"),
            ("Last read:", "last_read"),
            ("Progress:", "progress"),
        ):
            if body.startswith(prefix):
                fields[key] = body[len(prefix):].strip()
    book = fields.get("current_book", "")
    # Unfilled template ("[FILL IN — title and author]") counts as no book.
    if not book or book.startswith("["):
        return None
    last_read = _parse_date(fields.get("last_read"))
    return {
        "current_book": book,
        "started": fields.get("started") if _parse_date(fields.get("started")) else None,
        "last_read": last_read.isoformat() if last_read else None,
        "progress": fields.get("progress") or None,
        "stale_days": (date.today() - last_read).days if last_read else None,
    }


def _review_file_date(p) -> date | None:
    """Review date from a Weekly_Reviews filename: YYYY-MM-DD or ISO YYYY-WNN."""
    m = _REVIEW_DATE_RE.match(p.stem)
    if m:
        return _parse_date(p.stem)
    m = _REVIEW_WEEK_RE.match(p.stem)
    if m:
        try:
            # ISO week NN → that week's Sunday (the review-day convention).
            return date.fromisocalendar(int(m.group(1)), int(m.group(2)), 7)
        except ValueError:
            return None
    return None


def _parse_weekly_review() -> dict:
    """Most recent weekly review + countdown to the next Sunday due date."""
    today = date.today()
    next_due = today + timedelta(days=(6 - today.weekday()) % 7)
    last: date | None = None
    best_effective: date | None = None
    if WEEKLY_REVIEWS_DIR.exists():
        for p in WEEKLY_REVIEWS_DIR.glob("*.md"):
            d = _review_file_date(p)
            if d is None:
                continue  # README.md and other non-review files
            # Spec: pick the most recent by filename date OR mtime, whichever
            # is later — but report the filename date as the review date.
            mtime = datetime.fromtimestamp(p.stat().st_mtime).date()
            effective = max(d, mtime)
            # Ties on effective date (same-day mtimes) go to the later review.
            if (
                best_effective is None
                or effective > best_effective
                or (effective == best_effective and (last is None or d > last))
            ):
                best_effective = effective
                last = d
    days_since = (today - last).days if last else None
    return {
        "last_review_date": last.isoformat() if last else None,
        "days_since": days_since,
        "next_due": next_due.isoformat(),
        "days_until_next": (next_due - today).days,
        "overdue": days_since is not None and days_since > 7,
    }


@router.get("/brain-system")
def brain_system() -> dict:
    """Real data for the Brain/System focus card (Brain_System_Card_Spec.md).

    Every source degrades to null independently — a missing vault file must
    never 500 this endpoint.
    """
    return {
        "pending_upgrades": _parse_pending_upgrades(),
        "reading": _parse_reading_status(),
        "weekly_review": _parse_weekly_review(),
    }


# --- Manual tasks ("Awaiting your input", Manual_Tasks_Card_Spec.md) --------------
@router.get("/manual-tasks")
def manual_tasks() -> dict:
    """Files awaiting David's manual input. Auto-resolves: a filled file drops
    off the list on the next call — see backend/api/manual_tasks_detectors.py."""
    from backend.api.manual_tasks_detectors import collect_manual_tasks

    return collect_manual_tasks()


# --- Tasks summary ---------------------------------------------------------------
@router.get("/tasks-summary")
def tasks_summary() -> dict:
    """Open-task counts + the top 3 nearest items (GROUND zone compact view)."""
    md = vault.read_md(TASKS_FILE)
    open_count = 0
    top: list[dict] = []
    for section in ("This week", "Bigger items", "This month", "Waiting for"):
        bullets = markdown.parse_section_bullets(md, section)
        unchecked = [b for b in bullets if not b["checked"]]
        open_count += len(unchecked)
        if section == "This week":
            top = [{"text": b["text"], "section": section} for b in unchecked[:3]]
    # High-priority proxy: hard dates inside the next 7 days.
    high = 0
    for h in markdown.parse_hard_dates(md):
        d = h.get("date")
        if isinstance(d, str):
            d = _parse_date(d)
        if d and 0 <= (d - date.today()).days <= 7:
            high += 1
    return {"open": open_count, "high_priority": high, "top": top}
