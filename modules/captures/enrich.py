"""Claude enrich + voice auto-classify.

Runs the local ``claude -p`` CLI (David's Max subscription — no API key, no
per-call cost) over a capture's text and returns structured JSON.

Two prompt shapes, both LOCKED in the v3 build spec § b:
- **Voice** — classify into exactly one of Task / Park / Note and extract
  structure. Uses the EXACT template from the spec.
- **Image** — same shape minus ``category``/``task_text``, over ``ocr_text``
  instead of ``transcript``.

The model output is parsed defensively (``claude -p`` may wrap JSON in prose or
a code fence), mirroring the existing voice router's parser.
"""
from __future__ import annotations

import json
import re

from core.config import get_logger
from modules.agents.claude_cli import run_claude

logger = get_logger(__name__)


# Voice classify — EXACT template from spec § b ("Voice classify — prompt template").
_VOICE_PROMPT = """System: You classify a German or English voice note into exactly ONE category and
extract structure. Return ONLY valid JSON, no prose.
Categories:
- Task: an action David must take.
- Park: something to revisit later, not actionable now.
- Note: information worth keeping, no action needed.
Known projects for tagging: K&E, Ulli/Acebuche, Immos, Personal Brand.

Input:
  topic_tag: {topic_tag}
  transcript: {transcript}

Return:
{{
  "category": "Task|Park|Note",
  "project": "<one of the known projects, or null>",
  "tickers": [],
  "sectors": [],
  "ai_tags": ["..."],
  "title": "<= 8 word summary",
  "task_text": "<imperative phrasing if Task, else null>"
}}
"""

# Image enrich — "same shape minus category/task_text, over ocr_text" (spec § b).
_IMAGE_PROMPT = """System: You analyze a German or English captured image/screenshot via its OCR text and
extract structure. Return ONLY valid JSON, no prose.
Known projects for tagging: K&E, Ulli/Acebuche, Immos, Personal Brand.

Input:
  topic_tag: {topic_tag}
  ocr_text: {ocr_text}

Return:
{{
  "project": "<one of the known projects, or null>",
  "tickers": [],
  "sectors": [],
  "ai_tags": ["..."],
  "title": "<= 8 word summary"
}}
"""


def _parse_json(raw: str) -> dict:
    """Extract the first JSON object from ``claude -p`` output (tolerant)."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("no JSON object found in Claude output")
    return json.loads(match.group(0))


def _normalize(data: dict) -> dict:
    """Coerce the enrich result into a stable shape with safe defaults."""
    def _as_list(v) -> list:
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []

    project = data.get("project")
    if isinstance(project, str) and project.strip().lower() in ("", "null", "none"):
        project = None

    return {
        "category": data.get("category"),
        "project": project,
        "tickers": [t.upper() for t in _as_list(data.get("tickers"))],
        "sectors": _as_list(data.get("sectors")),
        "ai_tags": _as_list(data.get("ai_tags")),
        "title": (data.get("title") or "").strip() or None,
        "task_text": (data.get("task_text") or None) if isinstance(
            data.get("task_text"), str
        ) else None,
    }


def enrich_voice(topic_tag: str, transcript: str, timeout: int = 120) -> dict:
    """Classify + structure a voice note (Task / Park / Note)."""
    prompt = _VOICE_PROMPT.format(topic_tag=topic_tag or "", transcript=transcript or "")
    raw = run_claude(prompt, timeout=timeout)
    logger.info("enrich_voice raw: %s", raw[:300])
    result = _normalize(_parse_json(raw))
    # Guard: category must be one of the three; default to Note (no-action) when
    # the model returns something unexpected — Note never auto-creates a to-do.
    cat = (result.get("category") or "").strip().lower()
    result["category"] = {"task": "task", "park": "park", "note": "note"}.get(cat, "note")
    return result


def enrich_image(topic_tag: str, ocr_text: str, timeout: int = 120) -> dict:
    """Structure an image capture from its OCR text (category is always news)."""
    prompt = _IMAGE_PROMPT.format(topic_tag=topic_tag or "", ocr_text=ocr_text or "")
    raw = run_claude(prompt, timeout=timeout)
    logger.info("enrich_image raw: %s", raw[:300])
    result = _normalize(_parse_json(raw))
    result["category"] = "news"  # images are always stored as news (spec § b step 4)
    result["task_text"] = None
    return result
