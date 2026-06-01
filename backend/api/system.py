"""System API — vault stats + integration health, and a cache reset hook."""
from __future__ import annotations

from fastapi import APIRouter

from core import vault
from core.config import (
    VAULT_PATH, PROJECT_INDEX_FILE, INBOX_PATH,
)
from core import markdown
from modules.finance import loader
from modules.integrations import diagnostics
from modules.brand import videos
from modules.agents.skills.idea_validator import runner as iv
from modules.agents import background

router = APIRouter()


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
