"""Mission Control — the Command Center home view.

Registered as the default page by :mod:`dashboard.Home` (the navigation router).
``st.set_page_config`` lives in the router, so this module only renders content.
"""
import json
import os
import re
from datetime import date, datetime, timedelta

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from core import vault, markdown
from core.config import (
    SYSTEM_PATH,
    INBOX_PATH,
    READING_LIST_PATH,
    PROJECTS_PATH,
    DATA_DIR,
)
from modules.habits import health_journal
from modules.finance import money, portfolio, watchlist
from modules.projects import activity
from modules.integrations import calendar_ical, github, travel, whoop
from modules.agents.skills import idea_validator as iv

LAST_ACTIVE_FILE = DATA_DIR / "last_active.json"

inject_theme()
inject_shortcuts()

TASKS_PATH = SYSTEM_PATH / "Task_Command_Center.md"
PROJECT_INDEX_PATH = SYSTEM_PATH / "Project_Index.md"


# --- Cached wrappers for slow data sources (15 min TTL) ----------------------
@st.cache_data(ttl=900)
def _cached_recent_files(limit: int = 6, days: int = 14) -> list[dict]:
    return activity.recent_files(limit=limit, days=days)


@st.cache_data(ttl=900)
def _cached_recent_commits(limit: int = 3) -> list[dict]:
    return github.recent_commits(limit=limit)


def status_span(label: str, color: str) -> str:
    """Return an HTML span rendering a colored status label."""
    return (
        f'<span style="color:{color}; font-size:0.78rem; font-weight:600; '
        f'letter-spacing:0.05em;">{label}</span>'
    )


def strip_bold(text: str) -> str:
    """Remove markdown bold markers for a plain inline caption."""
    return text.replace("**", "").strip()


def today_entry_preview(raw: str) -> tuple[str, list[str]]:
    """Best-effort pull of (mood_line, first 2 note lines) from a journal entry."""
    mood = ""
    notes: list[str] = []
    in_notes = False
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("- mood:"):
            mood = stripped.lstrip("- ").strip()
        elif stripped.startswith("## Notes"):
            in_notes = True
        elif in_notes and stripped and not stripped.startswith("#"):
            notes.append(stripped)
            if len(notes) == 2:
                break
    return mood, notes


def _ago(dt: datetime) -> str:
    """Human relative time, e.g. 'just now', '12m ago', '3h ago', '2d ago'."""
    secs = (datetime.now() - dt).total_seconds()
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def _due_task_count(tasks_md: str, days: int = 7) -> int:
    """Count unchecked task bullets carrying an ISO date due within ``days``."""
    if not tasks_md:
        return 0
    today_d = date.today()
    horizon = today_d + timedelta(days=days)
    count = 0
    for line in tasks_md.split("\n"):
        s = line.strip()
        if not s.startswith("- ["):
            continue
        if "[x]" in s.lower():
            continue
        for m in re.finditer(r"(\d{4})-(\d{2})-(\d{2})", s):
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
            if today_d <= d <= horizon:
                count += 1
                break
    return count


def _quiet_project_count(days: int = 14) -> int:
    """Projects whose Project_Log.md has not been touched in ``days``+ days."""
    if not PROJECTS_PATH.exists():
        return 0
    cutoff = datetime.now().timestamp() - days * 86400
    count = 0
    for d in PROJECTS_PATH.iterdir():
        if not d.is_dir() or len(d.name) < 2 or not d.name[:2].isdigit():
            continue
        if d.name.startswith("98"):  # Ideen pipeline, not a tracked project
            continue
        log = d / "Project_Log.md"
        if log.exists() and log.stat().st_mtime < cutoff:
            count += 1
    return count


def _old_inbox_count(days: int = 7) -> int:
    cutoff = datetime.now().timestamp() - days * 86400
    return sum(1 for f in vault.list_files(INBOX_PATH) if f.stat().st_mtime < cutoff)


# ----------------------------------------------------------------------------
# 1. Header
# ----------------------------------------------------------------------------
st.title("Command Center")

today = date.today()
st.markdown(f"Good morning, David  ·  {today.strftime('%A, %B %d, %Y')}")

hard_dates = (
    '<div style="background-color:#1E1E1E; border:1px solid #2A2A2A; '
    'border-radius:8px; padding:10px 16px; margin-top:8px;">'
    '<span style="font-variant:small-caps; font-size:0.72rem; '
    'letter-spacing:0.08em; color:#9CA3AF;">Hard dates</span>'
    '<span style="color:#6B7280;">  ·  </span>'
    '<span style="color:#D1D5DB;">FFM apt 31.5</span>'
    '<span style="color:#047857;">  ·  </span>'
    '<span style="color:#D1D5DB;">Cards 5.6</span>'
    '<span style="color:#047857;">  ·  </span>'
    '<span style="color:#D1D5DB;">Defense 8.6</span>'
    '<span style="color:#047857;">  ·  </span>'
    '<span style="color:#D1D5DB;">Miami 11.6</span>'
    '<span style="color:#047857;">  ·  </span>'
    '<span style="color:#D1D5DB;">Evercore 1.7</span>'
    "</div>"
)
st.markdown(hard_dates, unsafe_allow_html=True)

# Read tasks once up front — used by the alert banner and the Today block.
tasks_md = vault.read_md(TASKS_PATH)

# --- Alert banner (simplified notifications) --------------------------------
_signals: list[str] = []
_due = _due_task_count(tasks_md)
if _due:
    _signals.append(f"{_due} task(s) due this week.")
_quiet = _quiet_project_count()
if _quiet:
    _signals.append(f"{_quiet} project(s) went quiet (no log in 14+ days).")
_old_inbox = _old_inbox_count()
if _old_inbox:
    _signals.append(f"{_old_inbox} inbox item(s) waiting >7 days.")
if _signals:
    st.warning("  \n".join(f"- {s}" for s in _signals))

# --- Continue where you left off --------------------------------------------
if LAST_ACTIVE_FILE.exists():
    try:
        _rec = json.loads(LAST_ACTIVE_FILE.read_text(encoding="utf-8"))
        _ts = datetime.fromisoformat(_rec["timestamp"])
        with st.container(border=True):
            c_last, c_resume = st.columns([4, 1])
            c_last.markdown(
                f"**Continue where you left off:** {_rec.get('name', '—')}  ·  {_ago(_ts)}"
            )
            with c_resume:
                try:
                    st.page_link("pages/03_Projects.py", label="Resume")
                except Exception:  # noqa: BLE001
                    pass
    except Exception:  # noqa: BLE001
        pass

st.write("")

# ----------------------------------------------------------------------------
# 1b. Calendar — next 5 events
# ----------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Calendar — next 5 events")
    if not calendar_ical.is_configured():
        st.caption("Calendar not configured. Add `OUTLOOK_ICAL_URL` to `.env`.")
    else:
        _events = calendar_ical.next_events(5)
        if not _events:
            st.caption("No upcoming events.")
        else:
            for _ev in _events:
                _start = _ev["start"]
                if isinstance(_start, datetime):
                    _when = _start.strftime("%a %d %b %H:%M")
                elif isinstance(_start, date):
                    _when = _start.strftime("%a %d %b (all day)")
                else:
                    _when = str(_start)
                _loc = f"  ·  📍 {_ev['location']}" if _ev.get("location") else ""
                st.markdown(f"**{_ev['title'] or '(untitled)'}** — {_when}{_loc}")

st.write("")

# ----------------------------------------------------------------------------
# 2. Row 1: Today + Quick capture
# ----------------------------------------------------------------------------
col_today, col_capture = st.columns([2, 1])

with col_today:
    with st.container(border=True):
        st.subheader("Today")
        if not tasks_md:
            st.error(f"Could not read {TASKS_PATH.name}: file is empty or missing")
            today_items = []
        else:
            today_items = markdown.parse_section_bullets(tasks_md, "This weekend")
            if not today_items:
                today_items = markdown.parse_section_bullets(tasks_md, "Today")
        for item in today_items[:6]:
            key = f"today_{item['line_index']}"
            new_val = st.checkbox(item["text"], value=item["checked"], key=key)
            if new_val != item["checked"]:
                new_md, _ = markdown.toggle_task(tasks_md, item["line_index"])
                vault.write_md(TASKS_PATH, new_md)
                st.toast("Saved")
                st.rerun()
        st.write("")
        try:
            st.page_link("pages/02_Tasks.py", label="View full task list")
        except Exception:
            st.markdown("[View full task list](#)")

with col_capture:
    with st.container(border=True):
        st.subheader("Quick capture")

        def _save_capture() -> None:
            """Append the captured text to the inbox and clear the field.

            Runs as a button callback (before widgets re-instantiate), so
            resetting the widget-backed session_state key is allowed.
            """
            text = st.session_state.get("quickcapture_input", "").strip()
            if not text:
                return
            try:
                vault.append_to_inbox(text, source="home")
                st.session_state["quickcapture_input"] = ""
                st.session_state["_capture_msg"] = "Saved to inbox"
            except Exception as exc:  # noqa: BLE001
                st.session_state["_capture_msg"] = f"Could not save to inbox: {exc}"

        st.text_area(
            "Drop a thought, idea, or link",
            key="quickcapture_input",
            height=120,
            label_visibility="collapsed",
            placeholder="Drop a thought, idea, or link...",
        )
        st.button("Save to inbox", on_click=_save_capture)
        msg = st.session_state.pop("_capture_msg", None)
        if msg:
            if msg.startswith("Could not"):
                st.error(msg)
            else:
                st.toast(msg)

st.write("")

# ----------------------------------------------------------------------------
# 3. Row 2: Projects
# ----------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Projects")
    projects_md = vault.read_md(PROJECT_INDEX_PATH)
    if not projects_md:
        st.error(f"Could not read {PROJECT_INDEX_PATH.name}: file is empty or missing")
        projects = []
    else:
        projects = markdown.parse_projects(projects_md)
    if projects:
        cols = st.columns(min(len(projects), 4))
        for col, proj in zip(cols, projects):
            with col:
                display_name = proj["name"].replace("_", " ")
                st.markdown(f"**{proj['id']}  {display_name}**")
                label, color = markdown.status_display(proj)
                st.markdown(status_span(label, color), unsafe_allow_html=True)
                next_step = strip_bold(proj["next_step"])
                if len(next_step) > 90:
                    next_step = next_step[:90].rstrip() + "…"
                st.caption(next_step or "—")
    else:
        st.caption("No projects found.")

st.write("")

# ----------------------------------------------------------------------------
# 4. Row 3: Finances (live data — phase 3)
# ----------------------------------------------------------------------------
def _euro(value) -> str:
    """Format euros for the snapshot metrics; em-dash when missing."""
    try:
        if value is None or (isinstance(value, float) and value != value):
            return "€ —"
        return f"€{value:,.0f}"
    except Exception:  # noqa: BLE001
        return "€ —"


col_portfolio, col_watchlist, col_money = st.columns(3)

with col_portfolio:
    with st.container(border=True):
        st.subheader("Portfolio")
        try:
            _pm = portfolio.summary_metrics()
            st.metric("Total value", _euro(_pm["total_value"]))
            st.metric("Positions", _pm["position_count"])
            st.caption("No live P&L (snapshot-based)")
        except Exception:  # noqa: BLE001
            st.metric("Total value", "€ —")
            st.metric("Positions", "—")
            st.caption("No live P&L (snapshot-based)")

with col_watchlist:
    with st.container(border=True):
        st.subheader("Watchlist")
        try:
            _wl = watchlist.load()
            st.write(f"{len(_wl)} on watch")
            for _it in _wl[:3]:
                _tk = str(_it.get("ticker", "")).strip().upper()
                _nm = str(_it.get("name", "")).strip()
                st.caption(f"{_tk} — {_nm}" if _nm else _tk)
        except Exception:  # noqa: BLE001
            st.write("Nike — research pending")
        try:
            st.page_link("pages/08_Watchlist.py", label="Open watchlist")
        except Exception:  # noqa: BLE001
            pass

with col_money:
    with st.container(border=True):
        st.subheader("Money snapshot")
        try:
            _cash = money.current_cash_balance()
            _fixed = money.monthly_fixed_estimate()
            _runway = money.runway_months(_cash, _fixed)
            st.metric("Cash", _euro(_cash))
            st.metric("Monthly fixed costs", _euro(_fixed))
            st.metric("Runway", "— months" if _runway is None else f"{_runway:.1f} months")
        except Exception:  # noqa: BLE001
            st.metric("Cash", "€ —")
            st.metric("Monthly fixed costs", "€ —")
            st.metric("Runway", "— months")

st.write("")

# ----------------------------------------------------------------------------
# 5. Row 4: Signals (Inbox / Waiting for / Habits / Travel)
# ----------------------------------------------------------------------------
col_inbox, col_waiting, col_habits, col_travel = st.columns(4)

with col_inbox:
    with st.container(border=True):
        st.subheader("Inbox")
        inbox_files = vault.list_files(INBOX_PATH)
        st.write(f"{len(inbox_files)} items waiting for triage")
        for f in inbox_files[:3]:
            st.caption(f.name)

with col_waiting:
    with st.container(border=True):
        st.subheader("Waiting for")
        waiting = markdown.parse_section_bullets(tasks_md, "Waiting for") if tasks_md else []
        if waiting:
            for item in waiting:
                st.write(f"- {item['text']}")
        else:
            st.write("Nothing currently logged.")

with col_habits:
    with st.container(border=True):
        st.subheader("Habits")
        st.checkbox("Mental math today")
        st.caption("Streak: 0 days")
        reading = markdown.parse_reading_list(vault.read_md(READING_LIST_PATH))
        if reading["reading_now"]:
            st.caption(f"Reading: {strip_bold(reading['reading_now'][0])}")

with col_travel:
    with st.container(border=True):
        st.subheader("Travel")
        _trips = travel.upcoming_trips()
        if not _trips:
            st.caption("No upcoming trips.")
        else:
            for _t in _trips[:2]:
                _dleft = travel.days_until(_t["date"])
                if _dleft is None:
                    _cd = ""
                elif _dleft >= 0:
                    _cd = f" · in {_dleft}d"
                else:
                    _cd = " · past"
                st.markdown(f"**{_t['destination']}**{_cd}")
                st.caption(_t["date"])

st.write("")

# ----------------------------------------------------------------------------
# 6. Row 5: Health (NEW)
# ----------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Health")
    col_whoop, col_journal, col_links = st.columns(3)

    with col_whoop:
        _w = whoop.summary()
        st.metric("Recovery", "—" if _w["recovery"] is None else f"{_w['recovery']:.0f} %")
        st.metric("Sleep", "—" if _w["sleep_hours"] is None else f"{_w['sleep_hours']:.1f} h")
        st.metric("HRV", "—" if _w["hrv"] is None else f"{_w['hrv']:.0f} ms")
        st.metric("Day Strain", "—" if _w["strain"] is None else f"{_w['strain']:.1f}")
        if not _w["configured"]:
            st.caption("_Whoop not configured._")

    with col_journal:
        st.markdown("**Today's journal**")
        entry = health_journal.read_today()
        if entry:
            mood, notes = today_entry_preview(entry["raw"])
            if mood:
                st.write(mood)
            for note in notes:
                st.caption(note)
        else:
            st.write("No entry yet today.")

    with col_links:
        try:
            st.page_link("pages/09_Health.py", label="Open health journal")
        except Exception:
            st.markdown("[Open health journal](#)")
        if st.button("Quick add", key="health_quick"):
            st.toast("Open the Health page to add an entry")

st.write("")

# ----------------------------------------------------------------------------
# 7. Row 6: Recent activity (vault files touched lately)
# ----------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Recent activity")

    # Highlight the latest Market Brief if produced within the last 7 days.
    try:
        from modules.agents import market_researcher as _mr

        _last_brief = _mr.last_run_date()
        if _last_brief and (date.today() - _last_brief) <= timedelta(days=7):
            st.success(
                f"📈 **Market Brief — {_last_brief.isoformat()}** · view on the Agents page"
            )
    except Exception:  # noqa: BLE001
        pass

    try:
        recent = _cached_recent_files(limit=6, days=14)
    except Exception:  # noqa: BLE001
        recent = []
    if recent:
        for i, r in enumerate(recent):
            c_name, c_open = st.columns([5, 1])
            with c_name:
                st.markdown(r["name"])
                st.caption(f"{r['mtime'].strftime('%Y-%m-%d %H:%M')}  ·  {_ago(r['mtime'])}")
            if c_open.button("Open", key=f"recent_{i}"):
                try:
                    os.startfile(str(r["path"]))  # noqa: S606 — Windows only, intentional
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not open {r['name']}: {exc}")
    else:
        st.caption("No recent file activity.")

    # Recent code commits (GitHub) — only when configured.
    if github.is_configured():
        _commits = _cached_recent_commits(limit=3)
        if _commits:
            st.markdown("**Recent code commits**")
            for _c in _commits:
                st.caption(f"`{_c['sha']}` {_c['repo']}: {_c['message']}")

    # Ideas in progress — N/12 validation stages each.
    try:
        _ideas = iv.list_ideas()
    except Exception:  # noqa: BLE001
        _ideas = []
    if _ideas:
        st.markdown("**Ideas in progress**")
        _n_stages = len(iv.STAGES)
        for _idea in _ideas:
            _done = _idea["stages_complete"]
            st.caption(
                f"💡 {_idea['name'].replace('_', ' ')} — {_done}/{_n_stages} stages"
            )
        try:
            st.page_link("pages/04_Ideas.py", label="Open Ideas")
        except Exception:  # noqa: BLE001
            pass
