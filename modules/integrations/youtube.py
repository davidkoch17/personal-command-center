"""YouTube Data API — fetch metadata for a saved video URL.

Returns ``None`` when ``YOUTUBE_API_KEY`` is missing, the URL has no parseable
video id, or the request fails.
"""
from __future__ import annotations

import os
import re

from core.config import get_logger

logger = get_logger(__name__)


def is_configured() -> bool:
    """True when the YouTube Data API key is present."""
    return bool(os.getenv("YOUTUBE_API_KEY"))


def video_metadata(url_or_id: str) -> dict | None:
    """Given a YouTube URL or id, fetch title/channel/thumbnail/url."""
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        return None
    vid = _extract_id(url_or_id)
    if not vid:
        return None
    try:
        import httpx

        r = httpx.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "snippet,contentDetails,statistics",
                "id": vid,
                "key": key,
            },
            timeout=15,
        )
        data = r.json()
        items = data.get("items", [])
        if not items:
            return None
        s = items[0]["snippet"]
        thumbs = s.get("thumbnails", {})
        thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
        return {
            "id": vid,
            "title": s["title"],
            "channel": s["channelTitle"],
            "thumbnail": thumb,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "embed_url": f"https://www.youtube.com/embed/{vid}",
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("youtube video_metadata failed: %s", e)
        return None


def _extract_id(s: str) -> str | None:
    s = (s or "").strip()
    if len(s) == 11 and "/" not in s:
        return s
    m = re.search(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})", s)
    return m.group(1) if m else None
