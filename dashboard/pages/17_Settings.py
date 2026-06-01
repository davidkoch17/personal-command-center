"""Settings — diagnostic view of configured paths and vault file freshness."""
from datetime import datetime
from pathlib import Path

import streamlit as st

from core import config
from dashboard._theme import inject_theme, inject_shortcuts
from modules.integrations import github, travel
from modules.integrations.diagnostics import run_all

st.set_page_config(page_title="Command Center", layout="wide")
inject_theme()
inject_shortcuts()
st.title("Settings")
st.caption("Configured paths and last-modified timestamps for key vault files.")


@st.cache_data(ttl=900)
def _cached_commits(limit: int = 10) -> list[dict]:
    return github.recent_commits(limit=limit)


def mtime_or_missing(p: Path) -> str:
    if not p.exists():
        return "missing"
    return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


# Integration diagnostics -----------------------------------------------------
with st.container(border=True):
    st.subheader("Integration diagnostics")
    if st.button("Run health check"):
        results = run_all()
        for r in results:
            status_color = {"ok": "#10B981", "not_configured": "#9CA3AF", "error": "#EF4444"}.get(r["status"], "#9CA3AF")
            status_label = {"ok": "OK", "not_configured": "Not configured", "error": "ERROR"}.get(r["status"], r["status"])
            st.markdown(
                f"<div style='display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #2a2e36'>"
                f"<span><strong>{r['name']}</strong></span>"
                f"<span style='color:{status_color}'>{status_label}{' — ' + r.get('detail','') if r.get('detail') else ''}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

# Cache control ---------------------------------------------------------------
with st.container(border=True):
    st.subheader("Cache")
    st.caption("Cached data (prices, news, commits, vault activity) refreshes every 15 minutes.")
    if st.button("Clear cache"):
        st.cache_data.clear()
        st.toast("Cache cleared")

# Info-barrier mode -----------------------------------------------------------
with st.container(border=True):
    st.subheader("Info-barrier (Evercore)")
    st.caption(
        "Once at Evercore, personal research on advised names/sectors is restricted. "
        f"Auto-engages on {config.EVERCORE_START_DATE}. Set the mode below."
    )
    import os as _os

    current_mode = _os.getenv("INFO_BARRIER", "auto").strip().lower()
    active = config.info_barrier_active()
    st.markdown(
        f"**Currently active:** {'YES' if active else 'no'}  ·  mode: `{current_mode}`"
    )
    mode = st.radio(
        "Mode",
        ["auto", "on", "off"],
        index=["auto", "on", "off"].index(current_mode) if current_mode in ("auto", "on", "off") else 0,
        horizontal=True,
        help="auto = date-based (engages at Evercore start); on/off = force.",
        key="info_barrier_mode",
    )
    restricted_raw = st.text_input(
        "Restricted tickers (comma-separated; blank = restrict ALL when active)",
        value=_os.getenv("RESTRICTED_TICKERS", ""),
        key="restricted_tickers",
    )
    if st.button("Save info-barrier settings"):
        try:
            config.set_env_var("INFO_BARRIER", mode)
            config.set_env_var("RESTRICTED_TICKERS", restricted_raw.strip())
            st.success("Saved. Reload Portfolio / Watchlist to see banners apply.")
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not save: {exc}")

# Keyboard shortcuts ----------------------------------------------------------
with st.expander("Keyboard shortcuts"):
    st.markdown(
        """
    - **Ctrl+1** — Home
    - **Ctrl+2** — Tasks
    - **Ctrl+3** — Projects
    - **Ctrl+I** — Inbox
    - **Ctrl+/** — Search
    """
    )


# Paths -----------------------------------------------------------------------
st.subheader("Paths")
paths = [
    ("Vault path", config.VAULT_PATH),
    ("Finance tracker path", config.FINANCE_TRACKER_FILE),
    ("Inbox path", config.INBOX_PATH),
    ("System path", config.SYSTEM_PATH),
]
st.table([{"Setting": name, "Path": str(p)} for name, p in paths])

# Key file freshness ----------------------------------------------------------
st.subheader("Key vault files")
key_files = [
    ("Project_Index", config.PROJECT_INDEX_FILE),
    ("Task_Command_Center", config.TASKS_FILE),
    ("Personal_Memory", config.SYSTEM_PATH / "Personal_Memory.md"),
    ("Decision_Log", config.SYSTEM_PATH / "Decision_Log.md"),
    ("Finance_Tracker", config.FINANCE_TRACKER_FILE),
    ("Reading_List", config.READING_LIST_PATH),
]
st.table(
    [{"File": name, "Last modified": mtime_or_missing(p)} for name, p in key_files]
)

# Market Researcher schedule -------------------------------------------------
st.subheader("Market Researcher schedule")
st.caption("The weekly agent auto-runs every Sunday at 19:00 Frankfurt time.")
st.markdown(
    """
To enable the Sunday 19:00 auto-run:

1. Open Task Scheduler (Win+R, type `taskschd.msc`).
2. Create Task → name **Market Researcher**.
3. Trigger: weekly, Sunday, 19:00.
4. Action: Start a program → point it at `run_market_researcher.bat` in the
   project directory (or `python` with arguments `-m modules.agents.market_researcher`,
   "Start in" set to the project dir).
5. Tick *Run whether user is logged on or not* for headless runs.

Until then, run manually from the **Agents** page (**Run now**) or by
double-clicking `run_market_researcher.bat`.
"""
)

# GitHub recent commits ------------------------------------------------------
st.subheader("GitHub")
if not github.is_configured():
    st.info("GitHub not configured. Add `GITHUB_PAT` and `GITHUB_USERNAME` to `.env`.")
else:
    commits = _cached_commits(limit=10)
    if not commits:
        st.caption("No commits found (or the request failed).")
    else:
        for c in commits:
            st.markdown(f"**{c['repo']}** `{c['sha']}` — [{c['message']}]({c['url']})")
            st.caption(c["date"])

# Travel ---------------------------------------------------------------------
st.subheader("Travel — upcoming trips")
_trips = travel.upcoming_trips()
if not _trips:
    st.info(
        "No trips found. Add them to `2_Personal/06_Travel/Trips.md` under "
        "`## Upcoming` as `### YYYY-MM-DD — Destination`."
    )
else:
    for t in _trips:
        dleft = travel.days_until(t["date"])
        countdown = "" if dleft is None else (f" · in {dleft} days" if dleft >= 0 else " · past")
        with st.container(border=True):
            st.markdown(f"**{t['destination']}** — {t['date']}{countdown}")
            for d in t["details"]:
                st.caption(d)
