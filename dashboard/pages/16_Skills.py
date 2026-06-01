"""Skills page — on-demand research skills (Earnings / Valuation / Model).

Phase 10a: deprecated from the sidebar and routes only by URL. Every run goes
background (see :func:`_launch_bg`); output lands on the Background Runs page.
The same skills are surfaced contextually on the Watchlist / Portfolio
workspaces and the Home "Quick Run" panel.
"""
from __future__ import annotations

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from core.config import get_logger
from modules.agents import background

logger = get_logger(__name__)

st.set_page_config(page_title="Command Center", layout="wide")
inject_theme()
inject_shortcuts()

st.title("Skills")
st.caption("On-demand research skills. Each runs once via `claude -p` — zero API cost.")


tab_earn, tab_val, tab_model = st.tabs(
    ["Earnings Reviewer", "Valuation Reviewer", "Model Builder"]
)


def _launch_bg(module_path: str, callable_name: str, args: list, label: str) -> None:
    """Launch a skill detached; surface a toast. Output is captured on the
    Background Runs page (truncated) rather than rendered here.

    Phase 10a: every skill run goes background — there is no synchronous mode.
    """
    try:
        background.launch(
            module_path=module_path,
            callable_name=callable_name,
            args=args,
            label=label,
        )
        st.toast(
            "Started in background — see Background Runs page or check vault "
            "output folder when complete."
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Background launch failed")
        st.error(f"Could not launch in background: {exc}")

# ---------------------------------------------------------------------------
# Earnings Reviewer
# ---------------------------------------------------------------------------
with tab_earn:
    st.subheader("Earnings Reviewer")
    ticker = st.text_input("Ticker", key="earn_ticker", placeholder="GOOGL")
    transcript = st.text_area(
        "Transcript (optional — paste from Seeking Alpha or company IR)",
        key="earn_transcript",
        height=200,
    )
    if st.button("Run review", key="earn_run", type="primary"):
        if not ticker.strip():
            st.warning("Enter a ticker first.")
        else:
            _launch_bg(
                "modules.agents.skills.earnings_reviewer", "review",
                [ticker.strip().upper(), transcript or None],
                f"Earnings {ticker.strip().upper()}",
            )

# ---------------------------------------------------------------------------
# Valuation Reviewer
# ---------------------------------------------------------------------------
with tab_val:
    st.subheader("Valuation Reviewer")
    v_ticker = st.text_input("Ticker", key="val_ticker", placeholder="NVDA")
    v_summary = st.text_area(
        "Your valuation summary", key="val_summary", height=200,
        placeholder="Method, multiples, target, conclusion…",
    )
    v_peers = st.text_input(
        "Peers (comma-separated)", key="val_peers", placeholder="AMD, AVGO, TSM"
    )
    if st.button("Review", key="val_run", type="primary"):
        if not v_ticker.strip() or not v_summary.strip():
            st.warning("Enter a ticker and a valuation summary first.")
        else:
            peers = [p.strip() for p in v_peers.split(",") if p.strip()]
            _launch_bg(
                "modules.agents.skills.valuation_reviewer", "review",
                [v_ticker.strip().upper(), v_summary, peers],
                f"Valuation {v_ticker.strip().upper()}",
            )

# ---------------------------------------------------------------------------
# Model Builder
# ---------------------------------------------------------------------------
with tab_model:
    st.subheader("Model Builder")
    m_ticker = st.text_input("Ticker", key="model_ticker", placeholder="TSLA")
    m_filings = st.text_area(
        "Latest filings summary", key="model_filings", height=160,
        placeholder="Key numbers from the latest 10-K/10-Q…",
    )
    m_assumptions = st.text_area(
        "Assumptions (raw JSON or bullet list)", key="model_assumptions", height=160,
        placeholder="- Revenue growth: 15%\n- Gross margin: 22%\n…",
    )
    if st.button("Build", key="model_run", type="primary"):
        if not m_ticker.strip():
            st.warning("Enter a ticker first.")
        else:
            _launch_bg(
                "modules.agents.skills.model_builder", "build",
                [m_ticker.strip().upper(), m_filings, m_assumptions],
                f"Model {m_ticker.strip().upper()}",
            )
