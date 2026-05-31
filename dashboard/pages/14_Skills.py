"""Skills page — on-demand research skills (Earnings / Valuation / Model)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st

from core.config import VAULT_PATH, get_logger
from modules.agents.skills import earnings_reviewer, model_builder, valuation_reviewer

logger = get_logger(__name__)

st.set_page_config(page_title="Skills", page_icon="🛠️", layout="wide")

st.title("🛠️ Skills")
st.caption("On-demand research skills. Each runs once via `claude -p` — zero API cost.")

INVESTING_DIR = VAULT_PATH / "4_Areas" / "Investing"


def _save_to_vault(subfolder: str, ticker: str, body: str) -> Path:
    """Write skill output into the vault via Python file I/O (per project rule)."""
    out_dir = INVESTING_DIR / subfolder
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_ticker = ticker.strip().upper().replace("/", "-") or "UNKNOWN"
    path = out_dir / f"{safe_ticker}_{date.today().isoformat()}.md"
    path.write_text(body, encoding="utf-8")
    return path


tab_earn, tab_val, tab_model = st.tabs(
    ["Earnings Reviewer", "Valuation Reviewer", "Model Builder"]
)

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
            with st.spinner(f"Reviewing {ticker} earnings via claude -p…"):
                try:
                    st.session_state["earn_output"] = earnings_reviewer.review(
                        ticker.strip().upper(), transcript or None
                    )
                except Exception as e:  # noqa: BLE001
                    logger.exception("Earnings review failed")
                    st.error(f"Review failed: {e}")

    if st.session_state.get("earn_output"):
        st.markdown(st.session_state["earn_output"])
        if st.button("💾 Save to vault", key="earn_save"):
            try:
                p = _save_to_vault("Earnings_Reviews", ticker, st.session_state["earn_output"])
                st.success(f"Saved to {p}")
            except Exception as e:  # noqa: BLE001
                st.error(f"Save failed: {e}")

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
            with st.spinner(f"Reviewing {v_ticker} valuation via claude -p…"):
                try:
                    st.session_state["val_output"] = valuation_reviewer.review(
                        v_ticker.strip().upper(), v_summary, peers
                    )
                except Exception as e:  # noqa: BLE001
                    logger.exception("Valuation review failed")
                    st.error(f"Review failed: {e}")

    if st.session_state.get("val_output"):
        st.markdown(st.session_state["val_output"])
        if st.button("💾 Save to vault", key="val_save"):
            try:
                p = _save_to_vault("Valuation_Reviews", v_ticker, st.session_state["val_output"])
                st.success(f"Saved to {p}")
            except Exception as e:  # noqa: BLE001
                st.error(f"Save failed: {e}")

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
            with st.spinner(f"Building {m_ticker} model spec via claude -p…"):
                try:
                    st.session_state["model_output"] = model_builder.build(
                        m_ticker.strip().upper(), m_filings, m_assumptions
                    )
                except Exception as e:  # noqa: BLE001
                    logger.exception("Model build failed")
                    st.error(f"Build failed: {e}")

    if st.session_state.get("model_output"):
        st.markdown(st.session_state["model_output"])
        if st.button("💾 Save to vault", key="model_save"):
            try:
                p = _save_to_vault("Models", m_ticker, st.session_state["model_output"])
                st.success(f"Saved to {p}")
            except Exception as e:  # noqa: BLE001
                st.error(f"Save failed: {e}")
