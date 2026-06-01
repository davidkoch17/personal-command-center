"""Career — Evercore prep overview (Phase 9b).

Per locked design §#6: a big start-date countdown, a four-metric status row
(model · technicals · admin · first-90-days), a toggleable prep-checklist preview,
recent `3_Career/` activity, and "Open Workspace ↗". The 10-section deep dive
lives in `_workspace_career.py`.
"""
from __future__ import annotations

import os
from datetime import date, datetime

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from dashboard._workspace_link import workspace_link
from core.config import CAREER_PATH, EVERCORE_START_DATE
from modules.career import tracker

st.set_page_config(page_title="Career", layout="wide")
inject_theme()
inject_shortcuts()
st.title("Career")

EVERCORE_START = date.fromisoformat(EVERCORE_START_DATE)
CURRENT_JOB = CAREER_PATH / "05_Current_Job"
MODEL_FILE = CURRENT_JOB / "3_Statement_Model.xlsx"
PLAN_FILE = CURRENT_JOB / "First_90_Days.md"

# --- Header: countdown ------------------------------------------------------
days = (EVERCORE_START - date.today()).days
st.markdown(
    f"<div style='font-size:2.4rem;font-weight:700;color:#10B981'>{days} days</div>"
    f"<div style='color:#9CA3AF'>until Evercore start ({EVERCORE_START_DATE})</div>",
    unsafe_allow_html=True,
)
st.write("")

# --- Status row -------------------------------------------------------------
onboarding = tracker.read_onboarding()
technicals = tracker.read_technicals()
admin_done = sum(1 for i in onboarding if i["checked"])
tech_done = sum(1 for i in technicals if i["checked"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("3-statement model", "Started" if MODEL_FILE.exists() else "Not started")
c2.metric("Technicals", f"{tech_done}/{len(technicals)}")
c3.metric("Onboarding admin", f"{admin_done}/{len(onboarding)}")
c4.metric("First 90 days", "Drafted" if PLAN_FILE.exists() else "Not started")

workspace_link("Open Workspace ↗", "career")
st.write("")

# --- Prep checklist preview (first 5, toggleable) ---------------------------
with st.container(border=True):
    st.subheader("Prep checklist")
    changed = False
    preview = onboarding[:5]
    for i, it in enumerate(preview):
        val = st.checkbox(it["text"], value=it["checked"], key=f"career_prep_{i}")
        if val != it["checked"]:
            onboarding[i]["checked"] = val
            changed = True
    if changed:
        tracker.save_onboarding(onboarding)
        st.rerun()

# --- Recent activity --------------------------------------------------------
with st.container(border=True):
    st.subheader("Recent activity — 3_Career/")
    files = []
    if CAREER_PATH.exists():
        for p in CAREER_PATH.rglob("*"):
            if p.is_file() and "archive" not in str(p).lower():
                files.append(p)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        st.caption("No files found under 3_Career/.")
    for i, p in enumerate(files[:3]):
        when = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        col_n, col_o = st.columns([5, 1])
        col_n.markdown(f"**{p.name}**")
        col_n.caption(when)
        if col_o.button("Open", key=f"career_recent_{i}"):
            try:
                os.startfile(str(p))  # noqa: S606
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not open: {exc}")
