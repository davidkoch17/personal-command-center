"""Portfolio workspace (hidden) — placeholder until Phase 9b.

URL: ``/workspace_portfolio``. The full deep-dive (Holdings / Allocations /
Performance / Attribution / Risk / Scenarios / Tax) is built in Phase 9b.
"""
import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts

st.set_page_config(page_title="Portfolio Workspace", layout="wide")
inject_theme()
inject_shortcuts()

st.title("Portfolio Workspace")
st.info("🚧 Workspace under construction — coming in Phase 9b.")
st.caption("Planned tabs: Holdings · Allocations · Performance · Attribution · Risk · Scenarios · Tax.")
