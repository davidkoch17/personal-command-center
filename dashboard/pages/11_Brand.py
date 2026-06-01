"""Brand — Content Studio overview (Phase 9b).

Per locked design §#5: a "+ New video" intake, a Pipeline kanban (default), and
horizontal-slicing tabs (All Concepts / Scripts / Shot Lists / Titles / Posting
Plans / Performance). Per-video deep dives open in a new tab
(`_workspace_brand_video.py?id=<folder>`). The existing YouTube-inspiration saver
is preserved in an expander.
"""
from __future__ import annotations

from datetime import date, datetime

import frontmatter
import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from dashboard._workspace_link import workspace_link
from core import vault
from core.config import BRAND_PATH
from modules.brand import videos
from modules.integrations import youtube

st.set_page_config(page_title="Brand", layout="wide")
inject_theme()
inject_shortcuts()
st.title("Brand — Content Studio")


def _ago(dt: datetime) -> str:
    secs = (datetime.now() - dt).total_seconds()
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


# --- + New video ------------------------------------------------------------
with st.expander("➕ New video", expanded=False):
    with st.form("new_video_form", clear_on_submit=True):
        v_title = st.text_input("Title", placeholder="e.g. How I run my week from one dashboard")
        v_platform = st.selectbox("Target platform", ["YouTube", "Instagram", "TikTok", "Multi"])
        v_concept = st.text_area("One-line concept", height=80)
        v_submit = st.form_submit_button("Create video", type="primary")
    if v_submit:
        if not v_title.strip():
            st.warning("Enter a title.")
        else:
            try:
                folder = videos.create_video(v_title.strip(), v_platform, v_concept.strip())
                st.toast(f"Created {folder.name}", icon="✅")
                st.rerun()
            except FileExistsError:
                st.error("A video with that title already exists.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not create video: {exc}")


all_videos = videos.list_videos()

tabs = st.tabs([
    "Pipeline", "All Concepts", "All Scripts", "All Shot Lists",
    "All Titles", "All Posting Plans", "Performance",
])

# --- Tab 1: Pipeline kanban -------------------------------------------------
with tabs[0]:
    if not all_videos:
        st.info("No videos yet. Use **➕ New video** to start one.")
    else:
        cols = st.columns(len(videos.STAGES))
        for col, stage in zip(cols, videos.STAGES):
            with col:
                st.markdown(f"**{stage}**")
                stage_vids = [v for v in all_videos if v["stage"] == stage]
                for v in stage_vids:
                    with st.container(border=True):
                        st.markdown(f"**{v['title']}**")
                        st.caption(f"{v['platform'] or '—'} · {_ago(v['modified'])}")
                        if stage != videos.STAGES[-1] and st.button("→ Advance", key=f"adv_{v['name']}"):
                            videos.advance_stage(v["path"])
                            st.rerun()
                        workspace_link("Open ↗", "brand_video", v["name"])
                if not stage_vids:
                    st.caption("—")


def _slice_tab(tab, filename: str, empty_msg: str) -> None:
    """Render a horizontal slice: one section file across all videos."""
    with tab:
        if not all_videos:
            st.info("No videos yet.")
            return
        for v in all_videos:
            content = videos.read_section(v["path"], filename).strip()
            with st.expander(f"{v['title']}  ·  {v['stage']}", expanded=False):
                st.markdown(content or f"_{empty_msg}_")
                workspace_link("Open this video ↗", "brand_video", v["name"])


_slice_tab(tabs[1], "01_Concept.md", "No concept yet.")
_slice_tab(tabs[2], "02_Script.md", "No script yet.")
_slice_tab(tabs[3], "03_Shot_List.md", "No shot list yet.")
_slice_tab(tabs[4], "06_Titles.md", "No titles yet.")
_slice_tab(tabs[5], "09_Posting_Plan.md", "No posting plan yet.")

# --- Tab 7: Performance -----------------------------------------------------
with tabs[6]:
    if not all_videos:
        st.info("No videos yet.")
    else:
        published = [v for v in all_videos if v["stage"] == "PUBLISHED"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Total videos", len(all_videos))
        c2.metric("Published", len(published))
        c3.metric("In production", len(all_videos) - len(published))
        st.divider()
        for v in published:
            with st.expander(f"{v['title']}", expanded=False):
                st.markdown(videos.read_section(v["path"], "10_Performance.md").strip() or "_No metrics logged._")
                workspace_link("Open this video ↗", "brand_video", v["name"])


# --- Inspirations (preserved from prior phase) ------------------------------
with st.expander("Inspirations (save a YouTube reference)", expanded=False):
    inspo_dir = BRAND_PATH / "02_Inspirations"
    if not youtube.is_configured():
        st.caption("YouTube not configured — add `YOUTUBE_API_KEY` to `.env` to fetch titles.")
    with st.form("save_youtube", clear_on_submit=True):
        yt_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=…")
        submitted_yt = st.form_submit_button("Save inspiration")
    if submitted_yt and yt_url.strip():
        meta = youtube.video_metadata(yt_url)
        if not meta:
            st.error("Could not fetch video metadata (check the URL and `YOUTUBE_API_KEY`).")
        else:
            try:
                inspo_dir.mkdir(parents=True, exist_ok=True)
                post = frontmatter.Post(
                    meta["title"], title=meta["title"], channel=meta["channel"],
                    url=meta["url"], thumbnail=meta["thumbnail"], video_id=meta["id"],
                    saved_date=date.today().isoformat(),
                )
                (inspo_dir / f"youtube_{meta['id']}.md").write_text(frontmatter.dumps(post), encoding="utf-8")
                st.success(f"Saved {meta['title']}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not save: {exc}")
    if inspo_dir.exists():
        yt_files = sorted(inspo_dir.glob("youtube_*.md"), reverse=True)
        cols = st.columns(3)
        for i, p in enumerate(yt_files):
            try:
                meta = frontmatter.load(p).metadata
            except Exception:  # noqa: BLE001
                continue
            with cols[i % 3]:
                if meta.get("thumbnail"):
                    st.image(meta["thumbnail"], use_container_width=True)
                st.markdown(f"**{meta.get('title', p.stem)}**")
                st.caption(meta.get("channel", ""))
