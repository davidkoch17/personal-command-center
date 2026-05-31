"""Lightweight full-text search across the vault."""
from pathlib import Path
from datetime import datetime
import re

from core.config import VAULT_PATH

SEARCHABLE_EXTENSIONS = {".md", ".txt"}
EXCLUDE_DIRS = {".obsidian", "9_Archive", "5_OneNote_Library", "00_Inbox"}
EXCLUDE_PATTERNS = {".bak"}


def _iter_files():
    for p in VAULT_PATH.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SEARCHABLE_EXTENSIONS:
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if any(p.name.endswith(suf) for suf in EXCLUDE_PATTERNS):
            continue
        yield p


def search(query: str, limit: int = 30) -> list[dict]:
    """Return matches with file path, snippet, modified time."""
    if not query.strip():
        return []
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    out = []
    for p in _iter_files():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        matches = list(pattern.finditer(text))
        if not matches:
            continue
        # Snippet from first match
        m = matches[0]
        start = max(0, m.start() - 80)
        end = min(len(text), m.end() + 120)
        snippet = text[start:end].replace("\n", " ")
        out.append({
            "path": p,
            "relative": str(p.relative_to(VAULT_PATH)),
            "snippet": snippet,
            "match_count": len(matches),
            "mtime": datetime.fromtimestamp(p.stat().st_mtime),
        })
    # Sort by match count desc, then mtime desc
    out.sort(key=lambda d: (-d["match_count"], -d["mtime"].timestamp()))
    return out[:limit]
