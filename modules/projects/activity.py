"""Vault activity tracker."""
from pathlib import Path
from datetime import datetime, timedelta
from core.config import VAULT_PATH


EXCLUDE_DIRS = {".obsidian", "0_Inbox", "00_Inbox", "9_Archive", "5_OneNote_Library", "OneNote", "Work_OS", "8_Others"}
EXCLUDE_PATTERNS = {".bak", ".tmp"}


def _iter_vault_files():
    for p in VAULT_PATH.rglob("*"):
        if not p.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if any(p.name.endswith(suf) for suf in EXCLUDE_PATTERNS):
            continue
        if p.name.startswith("~$") or p.name.startswith("."):
            continue
        yield p


def recent_files(limit: int = 10, days: int = 30) -> list[dict]:
    cutoff = datetime.now().timestamp() - days * 86400
    out = []
    for p in _iter_vault_files():
        mtime = p.stat().st_mtime
        if mtime < cutoff:
            continue
        out.append({"path": p, "name": p.name, "mtime": datetime.fromtimestamp(mtime)})
    out.sort(key=lambda d: d["mtime"], reverse=True)
    return out[:limit]


def activity_summary(days: int = 7) -> dict:
    """Files touched in the last N days, grouped by top-level area."""
    cutoff = datetime.now().timestamp() - days * 86400
    counts = {}
    for p in _iter_vault_files():
        if p.stat().st_mtime < cutoff:
            continue
        # First-level area under vault root
        rel = p.relative_to(VAULT_PATH)
        area = rel.parts[0] if rel.parts else "root"
        counts[area] = counts.get(area, 0) + 1
    return counts
