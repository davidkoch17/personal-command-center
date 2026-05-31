"""Mission Control — Personal Command Center home page (phase 2, live vault data)."""
from datetime import date

import streamlit as st

from core import vault, markdown
from core.config import SYSTEM_PATH, INBOX_PATH, READING_LIST_PATH
from modules.habits import health_journal
from modules.finance import money, portfolio, watchlist

st.set_page_config(
    page_title="Command Center",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

TASKS_PATH = SYSTEM_PATH / "Task_Command_Center.md"
PROJECT_INDEX_PATH = SYSTEM_PATH / "Project_Index.md"


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

st.write("")

# ----------------------------------------------------------------------------
# 2. Row 1: Today + Quick capture
# ----------------------------------------------------------------------------
tasks_md = vault.read_md(TASKS_PATH)

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
            st.page_link("pages/01_Tasks.py", label="View full task list")
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
            st.page_link("pages/06_Watchlist.py", label="Open watchlist")
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
# 5. Row 4: Signals (Inbox / Waiting for / Habits)
# ----------------------------------------------------------------------------
col_inbox, col_waiting, col_habits = st.columns(3)

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

st.write("")

# ----------------------------------------------------------------------------
# 6. Row 5: Health (NEW)
# ----------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Health")
    col_whoop, col_journal, col_links = st.columns(3)

    with col_whoop:
        st.metric("Recovery", "— %")
        st.metric("Sleep", "— h")
        st.metric("HRV", "— ms")
        st.metric("Day Strain", "—")
        st.caption("_Whoop API integration pending._")

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
            st.page_link("pages/07_Health.py", label="Open health journal")
        except Exception:
            st.markdown("[Open health journal](#)")
        if st.button("Quick add", key="health_quick"):
            st.toast("Open the Health page to add an entry")
