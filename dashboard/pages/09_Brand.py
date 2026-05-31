"""Brand — render the Personal Brand workspace from 1_Projects/05_Personal_Brand/."""
import re
from datetime import date, datetime
from pathlib import Path

import frontmatter
import streamlit as st

from core import vault
from core.config import PROJECTS_PATH
from modules.integrations import youtube
from modules.projects.ideas import _extract_h1

st.set_page_config(page_title="Brand", layout="wide")
st.title("Brand")

BRAND_PATH = PROJECTS_PATH / "05_Personal_Brand"


def first_paragraph(md: str) -> str:
    """Return the first non-heading, non-empty paragraph of the markdown."""
    for block in md.split("\n\n"):
        block = block.strip()
        if block and not block.startswith("#"):
            return block
    return ""


def first_sentence(md: str) -> str:
    """Return the first sentence of the first body paragraph."""
    para = first_paragraph(md)
    if not para:
        return ""
    m = re.split(r"(?<=[.!?])\s", para, maxsplit=1)
    return m[0].strip() if m else para


def mtime_str(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


# 1. Header -------------------------------------------------------------------
readme = vault.read_md(BRAND_PATH / "README.md")
if readme:
    summary = first_paragraph(readme) or readme.strip()
    st.markdown(summary)
else:
    st.info(
        f"File not found: {BRAND_PATH / 'README.md'}. "
        "Create it in the vault to populate this view."
    )

# 2. Strategy -----------------------------------------------------------------
with st.expander("Strategy", expanded=False):
    strategy_files = vault.list_files(BRAND_PATH / "01_Strategy")
    st.caption(f"{len(strategy_files)} strategy file(s)")
    if strategy_files:
        st.markdown(vault.read_md(strategy_files[0]))
    else:
        st.info(
            f"No strategy files yet. Add markdown to {BRAND_PATH / '01_Strategy'}"
        )

# 3. Inspirations -------------------------------------------------------------
with st.expander("Inspirations", expanded=False):
    inspo_dir = BRAND_PATH / "02_Inspirations"

    # Save a YouTube inspiration --------------------------------------------
    st.markdown("**Save a YouTube inspiration**")
    if not youtube.is_configured():
        st.caption("YouTube not configured — add `YOUTUBE_API_KEY` to `.env` to fetch titles.")
    with st.form("save_youtube", clear_on_submit=True):
        yt_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=…")
        submitted_yt = st.form_submit_button("Save inspiration")
    if submitted_yt:
        if not yt_url.strip():
            st.warning("Paste a YouTube URL first.")
        else:
            meta = youtube.video_metadata(yt_url)
            if not meta:
                st.error("Could not fetch video metadata (check the URL and `YOUTUBE_API_KEY`).")
            else:
                try:
                    inspo_dir.mkdir(parents=True, exist_ok=True)
                    post = frontmatter.Post(
                        meta["title"],
                        title=meta["title"],
                        channel=meta["channel"],
                        url=meta["url"],
                        thumbnail=meta["thumbnail"],
                        video_id=meta["id"],
                        saved_date=date.today().isoformat(),
                    )
                    out_path = inspo_dir / f"youtube_{meta['id']}.md"
                    out_path.write_text(frontmatter.dumps(post), encoding="utf-8")
                    st.success(f"Saved {out_path.name}")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not save: {exc}")

    # Gallery of saved videos + other inspiration files ---------------------
    if inspo_dir.exists():
        yt_files = sorted(inspo_dir.glob("youtube_*.md"), reverse=True)
        if yt_files:
            st.markdown("**Saved videos**")
            cols = st.columns(3)
            for i, p in enumerate(yt_files):
                try:
                    post = frontmatter.load(p)
                    meta = post.metadata
                except Exception:  # noqa: BLE001
                    continue
                with cols[i % 3]:
                    if meta.get("thumbnail"):
                        st.image(meta["thumbnail"], use_container_width=True)
                    st.markdown(f"**{meta.get('title', p.stem)}**")
                    st.caption(meta.get("channel", ""))
                    if meta.get("url"):
                        with st.expander("Watch"):
                            st.video(meta["url"])

        other = [p for p in sorted(inspo_dir.iterdir()) if not p.name.startswith("youtube_")]
        if other:
            st.markdown("**Other inspiration files**")
            for p in other:
                st.markdown(f"- **{p.name}** — {mtime_str(p)}")
        if not yt_files and not other:
            st.caption("Nothing here yet.")
    else:
        st.caption("No inspirations saved yet. Use the form above to add one.")

# 4. Video idea queue ---------------------------------------------------------
with st.container(border=True):
    st.subheader("Video idea queue")
    video_files = vault.list_files(BRAND_PATH / "03_Video_Ideas")
    if video_files:
        for p in video_files:
            md = vault.read_md(p)
            title = _extract_h1(md) or p.stem.replace("_", " ")
            desc = first_sentence(md)
            st.markdown(f"**{title}**  ·  {mtime_str(p)}")
            if desc:
                st.caption(desc)
    else:
        st.info(
            "No video ideas captured yet. Add a markdown file to "
            "1_Projects/05_Personal_Brand/03_Video_Ideas/"
        )

# 5. Production pipeline -------------------------------------------------------
with st.container(border=True):
    st.subheader("Production pipeline")
    pipeline_dir = BRAND_PATH / "04_Production_Pipeline"
    pipeline_md = vault.read_md(pipeline_dir / "pipeline.md")
    if pipeline_md:
        st.markdown(pipeline_md)
    else:
        pipeline_files = vault.list_files(pipeline_dir)
        if pipeline_files:
            for p in pipeline_files:
                st.markdown(f"- **{p.name}** — {mtime_str(p)}")
        else:
            st.info(
                f"No production items yet. Add files to {pipeline_dir}"
            )

# 6. Published log ------------------------------------------------------------
with st.container(border=True):
    st.subheader("Published log")
    published_dir = BRAND_PATH / "06_Published"
    if published_dir.exists():
        entries = sorted(published_dir.iterdir())
        if entries:
            rows = [{"File": p.name, "Last modified": mtime_str(p)} for p in entries]
            st.table(rows)
        else:
            st.caption("Nothing published yet.")
    else:
        st.info(
            f"File not found: {published_dir}. "
            "Create it in the vault to populate this view."
        )
