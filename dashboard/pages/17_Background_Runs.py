"""Background Runs — status of detached skill / agent runs.

Long skill and agent runs (idea validation, market researcher, finance skills)
can be launched detached via :mod:`modules.agents.background`. This page lists
recent runs with status, duration, and log output.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from modules.agents import background

st.set_page_config(page_title="Background Runs", page_icon="🛰️", layout="wide")
inject_theme()
inject_shortcuts()

st.title("🛰️ Background Runs")
st.caption(
    "Detached skill / agent runs. They keep running even if you close the page — "
    "come back here to check status and read logs."
)

_STATUS_BADGE = {
    "running": ("⟳ running", "#F59E0B"),
    "completed": ("✓ completed", "#10B981"),
    "failed": ("✗ failed", "#EF4444"),
    "unknown": ("? unknown", "#6B7280"),
}


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _duration(run: dict) -> str:
    start = _parse_iso(run.get("started_at"))
    if not start:
        return "—"
    end = _parse_iso(run.get("completed_at")) or _parse_iso(run.get("failed_at"))
    if not end:
        return "running…"
    secs = (end - start).total_seconds()
    if secs < 60:
        return f"{secs:.0f}s"
    if secs < 3600:
        return f"{secs / 60:.1f} min"
    return f"{secs / 3600:.1f} h"


top_l, top_r = st.columns([4, 1])
with top_l:
    st.markdown("**Recent runs**")
with top_r:
    if st.button("🔄 Refresh", key="bg_refresh"):
        st.rerun()

runs = background.list_recent_runs(20)
if not runs:
    st.info("No background runs yet. Launch one from the Ideas, Agents, or Skills pages.")
    st.stop()

for run in runs:
    run_id = run.get("run_id", "?")
    status = run.get("status", "unknown")
    label, color = _STATUS_BADGE.get(status, _STATUS_BADGE["unknown"])

    with st.container(border=True):
        c_label, c_status, c_dur = st.columns([3, 1, 1])
        with c_label:
            st.markdown(f"**{run_id}**")
            started = run.get("started_at") or run.get("launched_at") or "—"
            st.caption(f"started {started}")
        with c_status:
            st.markdown(
                f'<span style="color:{color}; font-weight:600;">{label}</span>',
                unsafe_allow_html=True,
            )
        with c_dur:
            st.caption(f"⏱ {_duration(run)}")

        if status == "failed" and run.get("error"):
            st.error(f"{run['error']}")
            if run.get("traceback"):
                with st.expander("Traceback"):
                    st.code(run["traceback"])
        elif status == "completed" and run.get("result"):
            st.caption(f"Result: {run['result']}")

        # Log file viewer
        log_path = Path(background.BG_LOG_DIR) / f"{run_id}.log"
        if log_path.exists():
            with st.expander("Log output"):
                try:
                    text = log_path.read_text(encoding="utf-8", errors="replace")
                    st.code(text[-8000:] if text else "(empty log)")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not read log: {exc}")
