"""Money workspace (hidden) — placeholder until Phase 9b.

URL: ``/workspace_money``. The full deep-dive (Cash Flow / Categories / Net Worth
/ Forecast / Budget / Tax / Transactions) is built in Phase 9b.
"""
import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts

st.set_page_config(page_title="Money Workspace", layout="wide")
inject_theme()
inject_shortcuts()

st.title("Money Workspace")
st.info("🚧 Workspace under construction — coming in Phase 9b.")
st.caption("Planned tabs: Cash Flow · Categories · Net Worth · Forecast · Budget · Tax · Transactions.")
