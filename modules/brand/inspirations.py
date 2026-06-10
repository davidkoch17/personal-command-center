"""Inspirations board for the Brand page — reference reels + notes.

Reads Markdown notes in ``05_Personal_Brand/02_Inspirations/``. Each note is one
inspiration card: a reel/video reference plus *what to steal* from it (hook,
pacing, edit style). The board is a scaffold David fills in — per the Brand
``CLAUDE.md``, creative direction (voice, taste, what to make) is his, not
Claude's. All writes use Python file I/O (OneDrive-safe) via ``core.vault``.
"""
from __future__ import annotations

from pathlib import Path

import frontmatter

from core.config import BRAND_PATH
from core.vault import write_md

INSPIRATIONS_PATH = BRAND_PATH / "02_Inspirations"


def list_inspirations() -> list[dict]:
    """All inspiration notes as cards, newest filename last (alpha order).

    Files starting with ``_`` (e.g. ``_README.md``) are treated as board docs,
    not cards, and skipped.
    """
    if not INSPIRATIONS_PATH.exists():
        return []
    out: list[dict] = []
    for p in sorted(INSPIRATIONS_PATH.glob("*.md")):
        if p.name.startswith("_"):
            continue
        try:
            post = frontmatter.load(p)
            meta = dict(post.metadata)
            body = post.content
        except Exception:  # noqa: BLE001 — never let one bad note break the board
            meta, body = {}, p.read_text(encoding="utf-8")
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        out.append({
            "name": p.stem,
            "title": meta.get("title", p.stem.replace("_", " ")),
            "url": meta.get("url", ""),
            "platform": meta.get("platform", ""),
            "tags": tags,
            "notes": (body or "").strip(),
        })
    return out


# --- Board scaffolding -------------------------------------------------------
# Seeds an empty board with a README + a few clearly-marked EXAMPLE cards that
# demonstrate the format. The examples are templates, not David's taste — he
# replaces them with real references. Seeding never overwrites existing notes.

_README = """# Inspirations Board — Personal Brand

Reference reels + notes. Each `.md` file here is one inspiration **card** shown on
the Brand page (Inspirations tab). Files starting with `_` (like this one) are
board docs, not cards.

## Card format

```
---
title: Short name for the reference
url: https://...            # link to the reel / video
platform: IG | YouTube | TikTok
tags: hook, pacing, edit-style
---

**What to steal:** the specific thing that works (the hook structure, the cut
rhythm, the way they open). Be concrete and executable.
```

> Creative direction — what your brand is, your voice, what you want to make — is
> **yours**. Think about that in Miro / OneNote. This board only captures *craft*
> references you want to learn from. Replace the EXAMPLE cards below with your own.
"""

_EXAMPLES = {
    "Example_Hook_Style.md": frontmatter.Post(
        "**What to steal:** the first 3 seconds — a single bold claim on screen "
        "before any face appears, so the scroll stops before the intro even starts.\n\n"
        "**Replace this** with a real reel whose hook you want to copy.",
        title="EXAMPLE — Hook style",
        url="https://...",
        platform="IG",
        tags=["hook", "open"],
    ),
    "Example_Edit_Pacing.md": frontmatter.Post(
        "**What to steal:** cut-on-motion pacing — every sentence is a new shot, "
        "no shot held longer than ~2s, zero dead air.\n\n"
        "**Replace this** with a real reel whose edit rhythm you want to copy.",
        title="EXAMPLE — Edit pacing",
        url="https://...",
        platform="YouTube",
        tags=["pacing", "edit-style"],
    ),
    "Example_Storytelling.md": frontmatter.Post(
        "**What to steal:** open-loop storytelling — pose the payoff up front, "
        "then withhold it until the last beat so people watch to completion.\n\n"
        "**Replace this** with a real video whose structure you want to copy.",
        title="EXAMPLE — Storytelling structure",
        url="https://...",
        platform="YouTube",
        tags=["structure", "retention"],
    ),
}


def seed_board() -> list[str]:
    """Create the README + EXAMPLE cards if missing. Returns files written.

    The example cards render as live cards (clearly titled ``EXAMPLE — ...``) so
    the board isn't empty on first open and the format is self-documenting;
    David replaces them with real references. Existing files are never
    overwritten.
    """
    INSPIRATIONS_PATH.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    readme = INSPIRATIONS_PATH / "_README.md"
    if not readme.exists():
        write_md(readme, _README)
        written.append(readme.name)

    for fname, post in _EXAMPLES.items():
        target = INSPIRATIONS_PATH / fname
        if not target.exists():
            write_md(target, frontmatter.dumps(post))
            written.append(fname)
    return written
