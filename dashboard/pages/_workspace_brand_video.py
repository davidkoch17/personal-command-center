"""Per-video Brand workspace (hidden) — placeholder until Phase 9b.

URL: ``/workspace_brand_video?id=<video_name>``. The full per-video workspace
(concept / script / shot list / filming notes / titles / description / posting
plan / performance / Ask Claude) is built in Phase 9b.
"""
import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts

st.set_page_config(page_title="Brand Video Workspace", layout="wide")
inject_theme()
inject_shortcuts()

video = st.query_params.get("id")
st.title(f"Brand Video — {video.replace('_', ' ')}" if video else "Brand Video Workspace")
st.info("🚧 Workspace under construction — coming in Phase 9b.")
st.caption("Planned: concept · script · shot list · filming notes · titles · description · posting plan · performance.")
