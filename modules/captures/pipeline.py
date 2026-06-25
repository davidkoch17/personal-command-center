"""Process a single capture end-to-end: read sidecar -> OCR/transcribe ->
Claude enrich -> route (approval model B) -> insert into SQLite.

The original media file is never touched (it is the backup). The DB row is the
source of truth.

**Approval model B (Hybrid, LOCKED 2026-06-24, spec § b):**
- News (image) with a clear ticker match -> auto-surface into Connected News
  immediately, ``status='approved-auto'`` (unreviewed; David curates after).
- News with no ticker / low confidence -> ``status='pending'`` until reviewed.
- Voice **Task** and **Park** -> always require review: stored as a capture with
  ``status='pending'``; NOT inserted into ``tasks``/``park_queue`` until David
  approves (no half-baked to-dos auto-appended).
- Voice **Note** -> ``status='approved-auto'`` and auto-filed into ``notes``
  (info, no action — harmless to surface).
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from core.config import get_logger
from modules.captures import db
from modules.captures.enrich import enrich_image, enrich_voice
from modules.captures.ocr import OCRUnavailable, ocr_image
from modules.captures.transcribe import TranscriptionUnavailable, transcribe_audio

logger = get_logger(__name__)

# A "clear ticker match": equities (AAPL, SAP, ADS.DE, BRK.B), indices (^GSPC),
# crypto/FX pairs (BTC-USD, EURUSD=X). Filters out enrich noise like "THE".
_TICKER_RE = re.compile(r"^\^?[A-Z]{1,6}([.\-=][A-Z0-9]{1,5})?$")


class CaptureSkip(Exception):
    """Raised when a capture can't be processed *yet* (media not synced, OCR /
    Whisper unavailable). The watcher logs and leaves it to retry next poll."""


def _valid_tickers(tickers: list[str]) -> list[str]:
    """Keep only ticker-shaped strings (drops obvious enrich noise)."""
    seen, out = set(), []
    for t in tickers:
        tu = t.strip().upper()
        if tu and tu not in seen and _TICKER_RE.match(tu):
            seen.add(tu)
            out.append(tu)
    return out


def read_sidecar(sidecar_path: Path) -> dict:
    """Parse a sidecar JSON file (raises on malformed JSON)."""
    return json.loads(sidecar_path.read_text(encoding="utf-8"))


def _ticker_rows(tickers: list[str], sectors: list[str]) -> list[dict]:
    """Pair tickers with a best-effort sector (first sector if 1:1 unknown)."""
    sector = sectors[0] if sectors else None
    return [{"ticker": t, "sector": sector} for t in tickers]


def process_capture(sidecar_path: Path) -> dict | None:
    """Ingest one capture from its sidecar JSON. Returns a summary dict.

    Returns ``None`` if the capture is already in the DB (idempotent). Raises
    :class:`CaptureSkip` for transient conditions (media file not yet synced,
    OCR/Whisper not installed) so the watcher retries on the next poll.
    """
    sidecar = read_sidecar(sidecar_path)
    capture_id = sidecar.get("id")
    if not capture_id:
        raise ValueError(f"sidecar {sidecar_path.name} has no 'id'")

    if db.capture_exists(capture_id):
        return None  # already ingested

    ctype = (sidecar.get("type") or "").lower()
    media_name = sidecar.get("file")
    media_path = sidecar_path.parent / media_name if media_name else None
    if not media_path or not media_path.exists():
        # OneDrive may sync the sidecar before the (larger) media file.
        raise CaptureSkip(
            f"media file {media_name!r} for {capture_id} not present yet — retry"
        )

    topic_tag = sidecar.get("topic_tag") or ""
    source_hint = sidecar.get("source_app")

    record: dict = {
        "id": capture_id,
        "captured_at": sidecar.get("captured_at"),
        "type": ctype,
        "topic_tag": topic_tag,
        "topic_slug": sidecar.get("topic_slug"),
        "ocr_text": None,
        "voice_transcript": None,
        "source_hint": source_hint,
        "routing_locked": 0,
        "image_path": None,
        "voice_path": None,
        "notes": None,
        "processed_at": datetime.now().isoformat(),
    }

    # --- extract text + enrich -------------------------------------------
    if ctype == "image":
        try:
            ocr_text = ocr_image(media_path)
        except OCRUnavailable as exc:
            raise CaptureSkip(f"OCR unavailable: {exc}") from exc
        record["ocr_text"] = ocr_text
        record["image_path"] = str(media_path)
        enriched = enrich_image(topic_tag, ocr_text)
    elif ctype == "voice":
        try:
            transcript, _lang = transcribe_audio(media_path)
        except TranscriptionUnavailable as exc:
            raise CaptureSkip(f"transcription unavailable: {exc}") from exc
        record["voice_transcript"] = transcript
        record["voice_path"] = str(media_path)
        enriched = enrich_voice(topic_tag, transcript)
    else:
        raise ValueError(f"unknown capture type {ctype!r} in {capture_id}")

    tickers = _valid_tickers(enriched.get("tickers", []))
    sectors = enriched.get("sectors", [])
    ai_tags = enriched.get("ai_tags", [])
    project = enriched.get("project")
    title = enriched.get("title")

    # --- route + approval model B ----------------------------------------
    category, status, routing = _route(ctype, enriched, tickers, project)
    record["ai_tags"] = ai_tags
    record["category"] = category
    record["status"] = status
    record["routing_suggestions"] = routing

    db.insert_capture(record, _ticker_rows(tickers, sectors))

    # Notes auto-file immediately; Task/Park wait for David's approval.
    note_id = None
    if ctype == "voice" and category == "note":
        body = record["voice_transcript"] or ""
        note_id = db.insert_note(title or topic_tag or "(untitled)", body, ai_tags, capture_id)

    summary = {
        "id": capture_id,
        "type": ctype,
        "category": category,
        "status": status,
        "tickers": tickers,
        "project": project,
        "title": title,
        "auto_filed_note_id": note_id,
    }
    logger.info("processed capture %s", summary)
    return summary


def _route(ctype: str, enriched: dict, tickers: list[str],
           project: str | None) -> tuple[str, str, dict]:
    """Decide (category, status, routing_suggestions) per approval model B."""
    if ctype == "image":
        category = "news"
        clear_ticker = bool(tickers)
        status = "approved-auto" if clear_ticker else "pending"
        routing = {
            "surface": "connected_news" if clear_ticker else "captures_pending",
            "reviewed": False,
            "tickers": tickers,
            "link_targets": ["watchlist", "hypothesis", "decision_log"],
            "title": enriched.get("title"),
            "reason": (
                "clear ticker match -> auto-surfaced (unreviewed)"
                if clear_ticker
                else "no clear ticker / low confidence -> pending review"
            ),
        }
        return category, status, routing

    # voice
    category = enriched.get("category", "note")
    if category == "task":
        status = "pending"  # always requires review before hitting the task list
        routing = {
            "route": "tasks",
            "requires_review": True,
            "project": project,
            "task_text": enriched.get("task_text"),
            "title": enriched.get("title"),
            "reason": "task -> review required before insert into tasks",
        }
    elif category == "park":
        status = "pending"  # always requires review before hitting park_queue
        routing = {
            "route": "park_queue",
            "requires_review": True,
            "title": enriched.get("title"),
            "reason": "park -> review required before insert into park_queue",
        }
    else:  # note
        category = "note"
        status = "approved-auto"
        routing = {
            "route": "notes",
            "requires_review": False,
            "title": enriched.get("title"),
            "reason": "note -> auto-filed (info, no action)",
        }
    return category, status, routing
