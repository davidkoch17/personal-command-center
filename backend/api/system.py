"""System API — vault stats + integration health, cache reset, OS file-open."""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core import vault
from core.config import (
    VAULT_PATH, PROJECT_INDEX_FILE, INBOX_PATH, get_logger,
    NEWS_CAPTURES_PATH, VOICE_NOTES_PATH, FINANCE_IMPORTS_DIR,
    CAPTURE_WATCHER_INTERVAL_SECONDS, WATCHLIST_UNIVERSE_FILE,
    EVERCORE_START_DATE, CAPTURE_KNOWN_PROJECTS,
)
from core import markdown
from modules.finance import loader
from modules.integrations import diagnostics
from modules.brand import videos
from modules.agents.skills.idea_validator import runner as iv
from modules.agents import background
from modules.system import checkpoints as checkpoints_mod

router = APIRouter()

logger = get_logger(__name__)

# Directories never searched when resolving loose paths (sync metadata, caches).
_SEARCH_SKIP_DIRS = {".obsidian", ".git", "__pycache__"}


@router.get("/status")
def status() -> dict:
    """Vault stats (counts + finance source freshness) and integration health."""
    projects = markdown.parse_projects(vault.read_md(PROJECT_INDEX_FILE))
    try:
        idea_count = len(iv.list_ideas())
    except Exception:  # noqa: BLE001
        idea_count = 0
    try:
        video_count = len(videos.list_videos())
    except Exception:  # noqa: BLE001
        video_count = 0
    return {
        "vault_path": str(VAULT_PATH),
        "vault_exists": VAULT_PATH.exists(),
        "finance_source_mtime": loader.source_mtime(),
        "counts": {
            "projects": len(projects),
            "ideas": idea_count,
            "brand_videos": video_count,
            "inbox_items": len(vault.list_files(INBOX_PATH)),
            "recent_runs": len(background.list_recent_runs(50)),
        },
        "integrations": diagnostics.run_all(),
    }


@router.get("/config")
def config() -> dict:
    """v3 configuration surfaced read-only on the Settings page (spec § f).

    Capture inbox paths + watcher cadence, the daily-snapshot time, the watchlist
    tier file, and Tailscale status. These are the active config values; most are
    code/Task-Scheduler constants (editing is out of scope for this phase).
    """
    return {
        "capture_paths": {
            "news_captures": str(NEWS_CAPTURES_PATH),
            "voice_notes": str(VOICE_NOTES_PATH),
            "finance_imports": str(FINANCE_IMPORTS_DIR),
            "watcher_interval_seconds": CAPTURE_WATCHER_INTERVAL_SECONDS,
        },
        "snapshot": {
            # Daily net-worth snapshot job (spec § c) — Windows Task Scheduler.
            "time": "18:00",
            "scheduler": "Windows Task Scheduler (daily)",
        },
        "watchlist": {
            "file": str(WATCHLIST_UNIVERSE_FILE),
            "tiers": ["Tier 1", "Tier 2", "Tier 3"],
        },
        "tailscale": {
            "configured": False,
            "note": "Set up in Phase G (Run + connect — Tailscale + PWA).",
        },
        "known_projects": CAPTURE_KNOWN_PROJECTS,
        "evercore_start": EVERCORE_START_DATE,
    }


@router.post("/clear-cache")
def clear_cache() -> dict:
    """No server-side cache layer yet — provided for frontend parity. Always ok."""
    return {"ok": True, "detail": "No server-side cache to clear."}


@router.get("/checkpoints")
def checkpoints() -> dict:
    """Reconciliation checkpoints, most recent first — see modules.system.checkpoints."""
    log = checkpoints_mod.list_checkpoints()
    return {"checkpoints": log, "latest": log[0] if log else None}


class OpenRequest(BaseModel):
    path: str


def _is_within_vault(p: Path) -> bool:
    try:
        p.resolve().relative_to(VAULT_PATH.resolve())
        return True
    except ValueError:
        return False


def _search_vault(raw: str) -> Path | None:
    """Find ``raw`` anywhere in the vault by tail-match.

    Callers pass loose paths (bare filenames like ``Finance_Tracker.xlsx``,
    partial tails like ``IdeaName/brief.md``); match the last component via
    rglob, then require every given component to line up from the end.
    """
    parts = PurePosixPath(raw.replace("\\", "/")).parts
    if not parts:
        return None
    matches = []
    for candidate in VAULT_PATH.rglob(parts[-1]):
        if _SEARCH_SKIP_DIRS.intersection(candidate.relative_to(VAULT_PATH).parts):
            continue
        if candidate.parts[-len(parts):] == parts:
            matches.append(candidate)
    return min(matches) if matches else None  # deterministic when ambiguous


def _resolve_open_target(raw: str) -> Path | None:
    """Absolute-under-vault -> vault-relative -> vault-wide tail search."""
    raw = raw.strip()
    if not raw:
        return None
    p = Path(raw)
    if p.is_absolute():
        return p if _is_within_vault(p) and p.exists() else None
    rel = VAULT_PATH / raw
    if rel.exists():
        return rel
    return _search_vault(raw)


@router.post("/open")
def open_in_os(req: OpenRequest) -> dict:
    """Open a vault file (or folder) in the host OS's default application.

    The server runs on David's own machine, so ``os.startfile`` here is the
    "click the file in Explorer" the browser sandbox can't do. Only paths that
    resolve inside the vault are allowed.
    """
    target = _resolve_open_target(req.path)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Not found in vault: {req.path}")
    if not _is_within_vault(target):
        raise HTTPException(status_code=403, detail="Path is outside the vault.")
    try:
        os.startfile(str(target))  # noqa: S606 - intentional, local-only server
    except OSError as exc:
        logger.warning("os-open failed for %s", target, exc_info=True)
        raise HTTPException(status_code=500, detail=f"OS could not open: {exc}") from exc
    return {"ok": True, "opened": str(target)}


# Suffixes the in-app editor may read/write. Vault writes happen exclusively
# through Python file I/O here (never the assistant's Edit/Write tools), with
# a .bak saved first — per the vault I/O rules in CLAUDE.md.
_EDITABLE_SUFFIXES = {".md", ".txt"}


class FileWriteRequest(BaseModel):
    path: str
    content: str


@router.get("/file")
def read_vault_file(path: str) -> dict:
    """Read a vault text file for the in-app editor.

    A path that doesn't resolve is NOT an error: the editor also opens
    files that don't exist yet (e.g. this week's review) — it gets
    ``exists: false`` and seeds the textarea from the task's template.
    """
    target = _resolve_open_target(path)
    if target is None or not target.is_file():
        return {"exists": False, "path": path, "content": ""}
    if target.suffix.lower() not in _EDITABLE_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"Not an editable text file: {target.suffix}")
    return {
        "exists": True,
        "path": str(target.relative_to(VAULT_PATH.resolve()) if target.is_absolute() else target),
        "content": target.read_text(encoding="utf-8"),
    }


@router.put("/file")
def write_vault_file(req: FileWriteRequest) -> dict:
    """Write a vault text file (in-app editor save). ``.bak`` saved first.

    Existing files resolve like /open (loose paths ok); a new file must be
    given vault-relative with an already-existing parent folder — the editor
    never silently creates directory trees.
    """
    target = _resolve_open_target(req.path)
    created = False
    if target is None:
        if Path(req.path).is_absolute():
            raise HTTPException(status_code=404, detail=f"Not found in vault: {req.path}")
        target = VAULT_PATH / req.path
        if not _is_within_vault(target):
            raise HTTPException(status_code=403, detail="Path is outside the vault.")
        if not target.parent.is_dir():
            raise HTTPException(status_code=404, detail=f"Parent folder missing: {target.parent.name}")
        created = True
    if not _is_within_vault(target):
        raise HTTPException(status_code=403, detail="Path is outside the vault.")
    if target.suffix.lower() not in _EDITABLE_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"Not an editable text file: {target.suffix}")
    if target.exists():
        bak = target.with_suffix(target.suffix + ".bak")
        bak.write_bytes(target.read_bytes())
    # newline="" disables newline translation — without it, write_text turns a
    # CRLF payload into CR CR LF on Windows. Normalize to LF for clean storage.
    target.write_text(req.content.replace("\r\n", "\n"), encoding="utf-8", newline="")
    logger.info("vault file %s: %s", "created" if created else "updated", target)
    return {"ok": True, "path": str(target), "created": created}
