"""Brand Content Studio skills (Phase 9b).

Claude-powered helpers for per-video work: hooks, script, shot list, titles,
description + tags, thumbnail copy, and Q&A. Transcription (cut suggestions) is
deferred to Phase 9.5 (needs local Whisper). All take a video folder NAME so they
run identically foreground or via background.launch.
"""
from __future__ import annotations

from modules.agents.claude_cli import run_claude
from modules.brand import videos


def _read(name: str, filename: str) -> str:
    return videos.read_section(videos.video_folder(name), filename)


def generate_hook_variants(video_name: str) -> str:
    """3-5 hook options for the video's concept."""
    concept = _read(video_name, "01_Concept.md")
    prompt = f"""You are a short-form content strategist. Generate 3-5 strong HOOK variants
(first 3 seconds) for this video. Each hook: punchy, scroll-stopping, distinct angle.

# Concept
{concept}

Output Markdown: a numbered list of hooks, each with a one-line note on why it works.
"""
    return run_claude(prompt, timeout=300)


def draft_first_pass_script(video_name: str) -> str:
    """First-draft script from the concept."""
    concept = _read(video_name, "01_Concept.md")
    prompt = f"""Write a first-pass script for this video in David's authentic, direct voice.

# Concept
{concept}

Output Markdown: [HOOK], [INTRO], [BODY with beats], [CTA]. Spoken-word style, tight pacing.
"""
    return run_claude(prompt, timeout=600)


def generate_shot_list(video_name: str) -> str:
    """Shot list derived from the script."""
    script = _read(video_name, "02_Script.md")
    prompt = f"""Generate a shot list from this script.

# Script
{script}

Output a Markdown table: Shot # | Visual | Location | Gear / framing | Notes.
"""
    return run_claude(prompt, timeout=300)


def generate_title_variants(video_name: str) -> str:
    """5 platform-aware title variants."""
    concept = _read(video_name, "01_Concept.md")
    status = videos.read_status(videos.video_folder(video_name))
    prompt = f"""Generate 5 title variants for platform "{status.get('platform','')}".

# Concept
{concept}

Output Markdown: numbered titles, each with a one-line rationale (curiosity / keyword / clarity).
"""
    return run_claude(prompt, timeout=300)


def generate_description_tags(video_name: str) -> str:
    """SEO description + hashtags per platform."""
    concept = _read(video_name, "01_Concept.md")
    status = videos.read_status(videos.video_folder(video_name))
    prompt = f"""Write a platform-specific SEO description + tags for platform "{status.get('platform','')}".

# Concept
{concept}

Output Markdown: a description paragraph, then a line of hashtags/keywords appropriate to the platform.
"""
    return run_claude(prompt, timeout=300)


def generate_thumbnail_copy(video_name: str) -> str:
    """3-5 thumbnail text options."""
    concept = _read(video_name, "01_Concept.md")
    prompt = f"""Generate 3-5 THUMBNAIL TEXT options (2-4 words each, high-contrast, emotional/curiosity).

# Concept
{concept}

Output Markdown: numbered options, each with a one-line note on the emotional angle.
"""
    return run_claude(prompt, timeout=300)


def ask_claude_about_video(video_name: str, question: str) -> str:
    """Q&A with all the video's files as context."""
    folder = videos.video_folder(video_name)
    parts = []
    for fname, _ in videos.SECTIONS:
        text = videos.read_section(folder, fname)
        if text.strip():
            parts.append(f"## {fname}\n\n{text}")
    context = "\n\n---\n\n".join(parts)
    prompt = f"""You are helping David with this video. Use the context below.

{context}

---

Question: {question}
"""
    return run_claude(prompt, timeout=300)
