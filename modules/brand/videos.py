"""Per-video folder helpers for the Brand Content Studio (Phase 9b).

Each video is a folder under ``1_Projects/05_Personal_Brand/03_Video_Ideas/<name>/``
holding the staged Markdown sections plus a ``00_Status.md`` front-matter file
that tracks pipeline stage, platform, and posting date. All writes are Python
file I/O (OneDrive-safe).
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import frontmatter

from core.config import BRAND_VIDEOS_PATH

STAGES = ["IDEAS", "SCRIPTING", "FILMING", "EDITING", "PUBLISHED"]

# (filename, human section title) — order is the workspace render order.
SECTIONS: list[tuple[str, str]] = [
    ("01_Concept.md", "Concept"),
    ("02_Script.md", "Script"),
    ("03_Shot_List.md", "Shot List"),
    ("04_Filming_Notes.md", "Filming Notes"),
    ("05_Transcript.md", "Transcript + cut suggestions"),
    ("06_Titles.md", "Titles"),
    ("07_Description_Tags.md", "Description + Tags"),
    ("08_Thumbnail_Copy.md", "Thumbnail Copy"),
    ("09_Posting_Plan.md", "Posting Plan"),
    ("10_Performance.md", "Performance"),
]


def _slug(title: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", title.strip()).strip("_")
    return s or "untitled"


def video_folder(name: str) -> Path:
    """Resolve a video folder by its folder name (already a slug)."""
    return BRAND_VIDEOS_PATH / name


def create_video(title: str, platform: str, concept: str) -> Path:
    """Create a new video folder with the 10 section files + status front-matter."""
    folder = BRAND_VIDEOS_PATH / _slug(title)
    folder.mkdir(parents=True, exist_ok=False)
    post = frontmatter.Post(
        f"Status for {title}",
        title=title,
        platform=platform,
        stage="IDEAS",
        posting_date="",
        created=datetime.now().isoformat(timespec="seconds"),
    )
    (folder / "00_Status.md").write_text(frontmatter.dumps(post), encoding="utf-8")
    seed = {
        "01_Concept.md": f"# Concept — {title}\n\n**Platform:** {platform}\n\n## One-liner\n{concept}\n\n"
                         f"## Hook\n\n## Audience\n\n## Why now\n\n## Key message\n",
        "02_Script.md": f"# Script — {title}\n\n",
        "03_Shot_List.md": f"# Shot List — {title}\n\n",
        "04_Filming_Notes.md": f"# Filming Notes — {title}\n\n",
        "05_Transcript.md": f"# Transcript — {title}\n\n_(Transcription deferred to Phase 9.5 — needs local Whisper.)_\n",
        "06_Titles.md": f"# Title variants — {title}\n\n",
        "07_Description_Tags.md": f"# Description + Tags — {title}\n\n",
        "08_Thumbnail_Copy.md": f"# Thumbnail copy — {title}\n\n",
        "09_Posting_Plan.md": f"# Posting Plan — {title}\n\n**Platform:** {platform}\n**Date:** TBD\n",
        "10_Performance.md": f"# Performance — {title}\n\n",
    }
    for fname, content in seed.items():
        (folder / fname).write_text(content, encoding="utf-8")
    return folder


def read_status(folder: Path) -> dict:
    """Parse 00_Status.md front-matter into a dict (defensive)."""
    p = folder / "00_Status.md"
    if not p.exists():
        return {"title": folder.name, "platform": "", "stage": "IDEAS", "posting_date": ""}
    try:
        post = frontmatter.load(p)
        meta = dict(post.metadata)
    except Exception:  # noqa: BLE001
        meta = {}
    meta.setdefault("title", folder.name)
    meta.setdefault("platform", "")
    meta.setdefault("stage", "IDEAS")
    meta.setdefault("posting_date", "")
    return meta


def set_stage(folder: Path, stage: str) -> None:
    """Write a new pipeline stage into 00_Status.md (preserving other fields)."""
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage}")
    p = folder / "00_Status.md"
    try:
        post = frontmatter.load(p) if p.exists() else frontmatter.Post("")
    except Exception:  # noqa: BLE001
        post = frontmatter.Post("")
    post["stage"] = stage
    p.write_text(frontmatter.dumps(post), encoding="utf-8")


def advance_stage(folder: Path) -> str:
    """Move the video to the next pipeline stage; returns the new stage."""
    cur = read_status(folder).get("stage", "IDEAS")
    idx = STAGES.index(cur) if cur in STAGES else 0
    nxt = STAGES[min(idx + 1, len(STAGES) - 1)]
    set_stage(folder, nxt)
    return nxt


def list_videos() -> list[dict]:
    """All video folders with status, newest-modified first."""
    if not BRAND_VIDEOS_PATH.exists():
        return []
    out = []
    for d in BRAND_VIDEOS_PATH.iterdir():
        if not d.is_dir() or d.name.startswith("_"):
            continue
        meta = read_status(d)
        out.append({
            "name": d.name,
            "path": d,
            "title": meta.get("title", d.name),
            "platform": meta.get("platform", ""),
            "stage": meta.get("stage", "IDEAS"),
            "posting_date": meta.get("posting_date", ""),
            "modified": datetime.fromtimestamp(d.stat().st_mtime),
        })
    return sorted(out, key=lambda x: x["modified"], reverse=True)


def read_section(folder: Path, filename: str) -> str:
    p = folder / filename
    return p.read_text(encoding="utf-8") if p.exists() else ""


def posting_log() -> dict:
    """All videos bucketed for the posting log / calendar surface.

    ``scheduled`` = has a posting_date and not yet published (soonest first);
    ``published`` = stage PUBLISHED (most-recent date first);
    ``undated`` = everything else still in the pipeline without a date.
    """
    scheduled: list[dict] = []
    published: list[dict] = []
    undated: list[dict] = []
    for v in list_videos():
        row = {
            "name": v["name"],
            "title": v["title"],
            "platform": v["platform"],
            "stage": v["stage"],
            "posting_date": v["posting_date"],
        }
        if v["stage"] == "PUBLISHED":
            published.append(row)
        elif v["posting_date"]:
            scheduled.append(row)
        else:
            undated.append(row)
    scheduled.sort(key=lambda r: r["posting_date"])
    published.sort(key=lambda r: r["posting_date"] or "", reverse=True)
    return {"scheduled": scheduled, "published": published, "undated": undated}
