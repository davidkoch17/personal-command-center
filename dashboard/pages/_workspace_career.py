"""Career workspace (hidden) — placeholder until Phase 9b.

URL: ``/workspace_career``. The full deep-dive (countdown · onboarding admin ·
technicals tracker · 3-statement model · first-90-days · deal pipeline · network
· strategy · documents · Ask Claude) is built in Phase 9b.
"""
import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts

st.set_page_config(page_title="Career Workspace", layout="wide")
inject_theme()
inject_shortcuts()

st.title("Career Workspace")
st.info("🚧 Workspace under construction — coming in Phase 9b.")
st.caption("Planned: Evercore countdown · onboarding admin · technicals refresh · first 90 days · network · strategy.")
