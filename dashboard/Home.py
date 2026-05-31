"""Mission Control — Personal Command Center home page (phase 1, placeholder data)."""
import datetime

import streamlit as st

st.set_page_config(
    page_title="Command Center",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Status label colors (per spec).
STATUS_COLORS = {
    "ON TRACK": "#10B981",
    "NEEDS ATTENTION": "#F59E0B",
    "AT RISK": "#EF4444",
    "DONE": "#9CA3AF",
}


def status_label(status: str) -> str:
    """Return an HTML span rendering a colored status label."""
    color = STATUS_COLORS.get(status, "#9CA3AF")
    return (
        f'<span style="color:{color}; font-size:0.78rem; font-weight:600; '
        f'letter-spacing:0.05em;">{status}</span>'
    )


# ----------------------------------------------------------------------------
# 1. Header
# ----------------------------------------------------------------------------
st.title("Command Center")

today = datetime.date.today()
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
col_today, col_capture = st.columns([2, 1])

with col_today:
    with st.container(border=True):
        st.subheader("Today")
        st.checkbox("FFM apartment decision")
        st.checkbox("PKV decision")
        st.checkbox("Capital gains screenshot")
        st.checkbox("Ulli deck scope")
        st.write("")
        try:
            st.page_link("pages/01_Tasks.py", label="View full task list")
        except Exception:
            st.markdown("[View full task list](#)")

with col_capture:
    with st.container(border=True):
        st.subheader("Quick capture")
        st.text_area(
            "Quick capture input",
            placeholder="Drop a thought, idea, or link...",
            label_visibility="collapsed",
        )
        if st.button("Save to inbox"):
            st.toast("Saved")

st.write("")

# ----------------------------------------------------------------------------
# 3. Row 2: Projects
# ----------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Projects")
    projects = [
        ("01  Thesis", "DONE", "Defense 8 June"),
        ("02  K&E", "ON TRACK", "Business plan + financial model"),
        ("03  Ulli", "NEEDS ATTENTION", "Final deck scope + assemble"),
        ("05  Brand", "ON TRACK", "Filming + inspo collection"),
    ]
    cols = st.columns(4)
    for col, (name, status, next_step) in zip(cols, projects):
        with col:
            st.markdown(f"**{name}**")
            st.markdown(status_label(status), unsafe_allow_html=True)
            st.caption(next_step)

st.write("")

# ----------------------------------------------------------------------------
# 4. Row 3: Finances
# ----------------------------------------------------------------------------
col_portfolio, col_watchlist, col_money = st.columns(3)

with col_portfolio:
    with st.container(border=True):
        st.subheader("Portfolio")
        st.metric("Total value", "€ —")
        st.metric("P&L (1d)", "—")
        st.metric("P&L (YTD)", "—")

with col_watchlist:
    with st.container(border=True):
        st.subheader("Watchlist")
        st.write("Nike — research pending")
        st.button("Add ticker")

with col_money:
    with st.container(border=True):
        st.subheader("Money snapshot")
        st.metric("Cash", "€ —")
        st.metric("Monthly fixed costs", "€ —")
        st.metric("Runway", "— months")

st.write("")

# ----------------------------------------------------------------------------
# 5. Row 4: Signals
# ----------------------------------------------------------------------------
col_inbox, col_waiting, col_habits = st.columns(3)

with col_inbox:
    with st.container(border=True):
        st.subheader("Inbox")
        st.write("0 items waiting for triage")

with col_waiting:
    with st.container(border=True):
        st.subheader("Waiting for")
        st.write("Nothing currently logged.")

with col_habits:
    with st.container(border=True):
        st.subheader("Habits")
        st.checkbox("Mental math today")
        st.caption("Streak: 0 days")

st.write("")

# ----------------------------------------------------------------------------
# 6. Row 5: Reading
# ----------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Reading")
    col_current, col_done = st.columns(2)
    with col_current:
        st.markdown("**Currently reading**")
        st.write("Man's Search for Meaning — Viktor Frankl")
        st.write("The Art of Thinking Clearly — Rolf Dobelli")
    with col_done:
        st.markdown("**Done in 2026**")
        st.metric("Books", "3")
