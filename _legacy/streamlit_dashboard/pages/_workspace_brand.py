"""Brand / Content Studio workspace (hidden) — placeholder until Phase 9b.

URL: ``/workspace_brand``. The full content-studio (pipeline + horizontal slices:
concepts / scripts / shot lists / titles / posting plans / performance) is built
in Phase 9b.
"""
import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts

st.set_page_config(page_title="Command Center", layout="wide")
inject_theme()
inject_shortcuts()

st.title("Brand Workspace")
st.info("Workspace under construction — coming in Phase 9b.")
st.caption("Planned: video pipeline (Ideas → Scripting → Filming → Editing → Published) + horizontal slices.")
