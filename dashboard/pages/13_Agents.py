"""Agents page — Market Researcher control panel."""
from __future__ import annotations

import os

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from core.config import get_logger
from modules.agents import market_researcher as mr
from modules.agents import background

logger = get_logger(__name__)

st.set_page_config(page_title="Agents", page_icon="🤖", layout="wide")
inject_theme()
inject_shortcuts()

st.title("🤖 Agents")

# ---------------------------------------------------------------------------
# Market Researcher card
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("📈 Market Researcher")
    st.caption(
        "Weekly equity research brief across David's watchlist universe. "
        "Runs inference on the Claude Max subscription via `claude -p` — zero API cost."
    )

    last = mr.last_run_date()
    nxt = mr.next_run_datetime()
    col1, col2 = st.columns(2)
    col1.metric("Last run", last.isoformat() if last else "Never")
    col2.metric("Next scheduled run", nxt.strftime("%a %Y-%m-%d %H:%M"))

    run_bg = st.checkbox(
        "Run in background", key="mr_run_bg",
        help="Launch detached so the dashboard stays interactive. Track it on the "
             "Background Runs page.",
    )
    if st.button("▶ Run now", type="primary", key="run_market_researcher"):
        if run_bg:
            try:
                info = background.launch(
                    module_path="modules.agents.market_researcher",
                    callable_name="run",
                    args=[],
                    label="Market Researcher",
                )
                st.toast(f"Started in background: {info['run_id']}", icon="🚀")
            except Exception as e:  # noqa: BLE001
                logger.exception("Background launch failed")
                st.error(f"Could not launch in background: {e}")
        else:
            with st.spinner(
                "Running Market Researcher — fetching data and calling claude -p. "
                "This can take a few minutes…"
            ):
                try:
                    path = mr.run()
                    st.toast(f"Brief written: {path.name}", icon="✅")
                    st.success(f"Brief written to {path}")
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    logger.exception("Market Researcher run failed")
                    st.error(f"Run failed: {e}")

    st.markdown("**Recent briefs**")
    briefs = mr.list_briefs(limit=8)
    if not briefs:
        st.info("No briefs yet. Click **Run now** or wait for the Sunday auto-run.")
    else:
        for b in briefs:
            with st.expander(f"Market Brief — {b.stem}"):
                try:
                    st.markdown(b.read_text(encoding="utf-8"))
                except Exception as e:  # noqa: BLE001
                    st.error(f"Could not read brief: {e}")
                if st.button("Open in editor", key=f"open_{b.stem}"):
                    try:
                        os.startfile(str(b))  # noqa: S606 - local Windows convenience
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Could not open file: {e}")

    if mr.HYPOTHESIS_FILE.exists():
        if st.button("Open Hypothesis Tracker", key="open_hypothesis"):
            try:
                os.startfile(str(mr.HYPOTHESIS_FILE))  # noqa: S606
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not open file: {e}")
    else:
        st.caption("Hypothesis Tracker will be created on the first run.")

# ---------------------------------------------------------------------------
# Schedule note
# ---------------------------------------------------------------------------
st.info(
    "Auto-runs every Sunday at 19:00 Frankfurt time (set via Windows Task "
    "Scheduler — see the Settings page / README for setup instructions)."
)
