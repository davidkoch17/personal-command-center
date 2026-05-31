"""Settings — diagnostic view of configured paths and vault file freshness."""
from datetime import datetime
from pathlib import Path

import streamlit as st

from core import config
from modules.integrations import github, travel

st.set_page_config(page_title="Settings", layout="wide")
st.title("Settings")
st.caption("Configured paths and last-modified timestamps for key vault files.")


def mtime_or_missing(p: Path) -> str:
    if not p.exists():
        return "missing"
    return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


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
    commits = github.recent_commits(limit=10)
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
