"""Per-video Brand workspace (hidden, new-tab) — Phase 9b.

URL: ``/workspace_brand_video?id=<folder>``. Renders the 10 video sections with
their Claude skills (hooks, script, shot list, titles, description+tags, thumbnail
copy, Q&A). Editable sections (filming notes, posting plan, performance) write
back to the video folder. Transcription is deferred to Phase 9.5.
"""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from dashboard._skillrun import run_skill
from core import vault
from modules.brand import videos

BRAND = "modules.agents.skills.brand"

st.set_page_config(page_title="Video Workspace", layout="wide")
inject_theme()
inject_shortcuts()

names = [v["name"] for v in videos.list_videos()]
vid = st.query_params.get("id")

if not vid or vid not in names:
    st.title("Video Workspace")
    if vid:
        st.warning(f"Unknown video: {vid}")
    if not names:
        st.info("No videos yet. Create one on the Brand page.")
        st.stop()
    chosen = st.selectbox("Pick a video", names)
    if st.button("Open"):
        st.query_params["id"] = chosen
        st.rerun()
    st.stop()

folder = videos.video_folder(vid)
status = videos.read_status(folder)


def _save_section(filename: str, text: str) -> None:
    vault.write_md(folder / filename, text)


def _editable(filename: str, title: str, height: int = 200) -> None:
    current = videos.read_section(folder, filename)
    edited = st.text_area(title, value=current, height=height, key=f"edit_{filename}",
                          label_visibility="collapsed")
    if st.button(f"Save {title}", key=f"save_{filename}"):
        _save_section(filename, edited)
        st.toast(f"Saved {title}", icon="✅")


# --- Header -----------------------------------------------------------------
st.title(f"🎬 {status.get('title', vid)}")
h1, h2, h3, h4 = st.columns(4)
h1.metric("Stage", status.get("stage", "IDEAS"))
h2.metric("Platform", status.get("platform", "—") or "—")
h3.metric("Posting date", status.get("posting_date", "—") or "—")
created = status.get("created", "")
h4.metric("Created", str(created)[:10] if created else "—")

cset1, cset2 = st.columns([2, 1])
with cset1:
    new_stage = st.selectbox("Set stage", videos.STAGES,
                             index=videos.STAGES.index(status.get("stage", "IDEAS"))
                             if status.get("stage") in videos.STAGES else 0)
    if new_stage != status.get("stage") and st.button("Update stage"):
        videos.set_stage(folder, new_stage)
        st.rerun()

# --- Section 1: Concept -----------------------------------------------------
with st.container(border=True):
    st.subheader("1 · Concept")
    st.markdown(videos.read_section(folder, "01_Concept.md") or "_No concept yet._")
    run_skill("Generate hook variants", BRAND, "generate_hook_variants", [vid], key="bv_hooks")

# --- Section 2: Script ------------------------------------------------------
with st.container(border=True):
    st.subheader("2 · Script")
    st.markdown(videos.read_section(folder, "02_Script.md") or "_No script yet._")
    run_skill("Draft first-pass script", BRAND, "draft_first_pass_script", [vid], key="bv_script")

# --- Section 3: Shot List ---------------------------------------------------
with st.container(border=True):
    st.subheader("3 · Shot List")
    st.markdown(videos.read_section(folder, "03_Shot_List.md") or "_No shot list yet._")
    run_skill("Generate shot list", BRAND, "generate_shot_list", [vid], key="bv_shots")

# --- Section 4: Filming Notes (editable) ------------------------------------
with st.container(border=True):
    st.subheader("4 · Filming Notes")
    _editable("04_Filming_Notes.md", "Filming Notes")

# --- Section 5: Transcript (deferred) ---------------------------------------
with st.container(border=True):
    st.subheader("5 · Transcript + cut suggestions")
    st.caption("Deferred to Phase 9.5 — needs local Whisper transcription.")

# --- Section 6: Titles ------------------------------------------------------
with st.container(border=True):
    st.subheader("6 · Titles")
    st.markdown(videos.read_section(folder, "06_Titles.md") or "_No titles yet._")
    run_skill("Generate title variants", BRAND, "generate_title_variants", [vid], key="bv_titles")

# --- Section 7: Description + Tags ------------------------------------------
with st.container(border=True):
    st.subheader("7 · Description + Tags")
    st.markdown(videos.read_section(folder, "07_Description_Tags.md") or "_None yet._")
    run_skill("Generate description + tags", BRAND, "generate_description_tags", [vid], key="bv_desc")

# --- Section 8: Thumbnail Copy ----------------------------------------------
with st.container(border=True):
    st.subheader("8 · Thumbnail Copy")
    st.markdown(videos.read_section(folder, "08_Thumbnail_Copy.md") or "_None yet._")
    run_skill("Generate thumbnail copy", BRAND, "generate_thumbnail_copy", [vid], key="bv_thumb")

# --- Section 9: Posting Plan (editable) -------------------------------------
with st.container(border=True):
    st.subheader("9 · Posting Plan")
    _editable("09_Posting_Plan.md", "Posting Plan", height=140)

# --- Section 10: Performance (editable) -------------------------------------
with st.container(border=True):
    st.subheader("10 · Performance")
    _editable("10_Performance.md", "Performance", height=140)

# --- Ask Claude about this video --------------------------------------------
with st.container(border=True):
    st.subheader("🤖 Ask Claude about this video")
    q = st.text_input("Question", key="bv_ask_q")
    run_skill("Ask", BRAND, "ask_claude_about_video", [vid, q], key="bv_ask",
              allow_background=False)
