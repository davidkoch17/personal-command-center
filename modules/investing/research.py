"""Per-name investing research helpers (Phase 9b).

Read/write free-text position notes, and filter the shared vault trackers
(Hypothesis_Tracker, Decision_Log, Market_Briefs) down to a single name. Used by
the Portfolio per-holding sub-view and the Watchlist per-ticker workspace.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from core.config import (
    DECISION_LOG_FILE,
    HYPOTHESIS_TRACKER_FILE,
    MARKET_BRIEFS_DIR,
    POSITION_NOTES_DIR,
)


def _safe_ticker(ticker: str) -> str:
    return "".join(c for c in (ticker or "").upper() if c.isalnum() or c in "._-") or "UNKNOWN"


def position_note_path(ticker: str) -> Path:
    """Path to the per-ticker research note (4_Areas/Investing/Position_Notes/<TICKER>.md)."""
    return POSITION_NOTES_DIR / f"{_safe_ticker(ticker)}.md"


def read_position_note(ticker: str) -> str:
    p = position_note_path(ticker)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def write_position_note(ticker: str, text: str) -> Path:
    """Save the per-ticker note via Python file I/O with a ``.bak`` backup."""
    p = position_note_path(ticker)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        shutil.copy2(p, p.with_suffix(".md.bak"))
    p.write_text(text, encoding="utf-8")
    return p


def _name_tokens(ticker: str, name: str = "") -> list[str]:
    toks = [t for t in [(ticker or "").upper(), *(name or "").split()] if len(t) >= 2]
    # de-dupe, preserve order
    seen, out = set(), []
    for t in toks:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def filter_hypotheses(ticker: str, name: str = "") -> list[str]:
    """Return Hypothesis_Tracker entry blocks that mention this name/ticker."""
    if not HYPOTHESIS_TRACKER_FILE.exists():
        return []
    text = HYPOTHESIS_TRACKER_FILE.read_text(encoding="utf-8")
    toks = _name_tokens(ticker, name)
    # Blocks start at a bold "**H..." or "**[TICKER]" marker.
    blocks = re.split(r"\n(?=\*\*\[?[A-Z0-9])", text)
    out = []
    for b in blocks:
        if any(re.search(rf"\b{re.escape(t)}\b", b, re.IGNORECASE) for t in toks):
            out.append(b.strip())
    return out


def filter_decisions(ticker: str, name: str = "") -> list[tuple[str, str]]:
    """Return Decision_Log entries (head, body) mentioning this name/ticker."""
    if not DECISION_LOG_FILE.exists():
        return []
    text = DECISION_LOG_FILE.read_text(encoding="utf-8")
    toks = _name_tokens(ticker, name)
    out = []
    for chunk in re.split(r"(?m)^##\s+", text)[1:]:
        head, _, body = chunk.partition("\n")
        blob = f"{head}\n{body}"
        if any(re.search(rf"\b{re.escape(t)}\b", blob, re.IGNORECASE) for t in toks):
            out.append((head.strip(), body.strip()))
    return out


def recent_signals(ticker: str, name: str = "", limit: int = 8) -> list[dict]:
    """Scan the last ``limit`` Market Briefs for lines mentioning this name.

    Returns ``[{"brief": "<date>", "lines": [..]}, ...]`` newest first.
    """
    if not MARKET_BRIEFS_DIR.exists():
        return []
    toks = _name_tokens(ticker, name)
    briefs = sorted(MARKET_BRIEFS_DIR.glob("*.md"), reverse=True)[:limit]
    out = []
    for bp in briefs:
        try:
            text = bp.read_text(encoding="utf-8")
        except OSError:
            continue
        hits = [
            ln.strip(" -*")
            for ln in text.splitlines()
            if ln.strip() and any(re.search(rf"\b{re.escape(t)}\b", ln, re.IGNORECASE) for t in toks)
        ]
        if hits:
            out.append({"brief": bp.stem, "lines": hits[:6]})
    return out
