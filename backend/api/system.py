"""System API — vault stats + integration health, cache reset, OS file-open."""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core import vault
from core.config import (
    VAULT_PATH, PROJECT_INDEX_FILE, INBOX_PATH, get_logger,
)
from core import markdown
from modules.finance import loader
from modules.integrations import diagnostics
from modules.brand import videos
from modules.agents.skills.idea_validator import runner as iv
from modules.agents import background

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


@router.post("/clear-cache")
def clear_cache() -> dict:
    """No server-side cache layer yet — provided for frontend parity. Always ok."""
    return {"ok": True, "detail": "No server-side cache to clear."}


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
