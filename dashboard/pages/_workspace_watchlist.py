"""Per-ticker Watchlist workspace (hidden) — placeholder until Phase 9b.

URL: ``/workspace_watchlist?id=<ticker>``. The full research dossier (status ·
hypotheses · chart · news · filings · comparables · signals · notes · model ·
decisions · Ask Claude) is built in Phase 9b.
"""
import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts

st.set_page_config(page_title="Watchlist Workspace", layout="wide")
inject_theme()
inject_shortcuts()

ticker = st.query_params.get("id")
st.title(f"Watchlist — {ticker.upper()}" if ticker else "Watchlist Workspace")
st.info("🚧 Workspace under construction — coming in Phase 9b.")
st.caption("Planned: status · hypotheses · chart · news · filings · comparables · signals · notes · model · decisions.")
