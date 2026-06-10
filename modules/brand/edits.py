"""'New edit' trigger — STUB for the future Remotion edit repo.

The Remotion edit pipeline lives in a separate repo that doesn't exist yet
(Active_Backlog C1). Until it's built, "New edit" just records the request to a
queue file and returns a stubbed response — no edit is produced. When the
Remotion repo lands, this is the single place to wire the real trigger.

Vault writes use Python file I/O (OneDrive-safe) via ``core.vault``.
"""
from __future__ import annotations

from datetime import datetime

from core.config import BRAND_PATH
from core.vault import write_md

EDITS_PATH = BRAND_PATH / "05_Edits"
EDIT_QUEUE_FILE = EDITS_PATH / "_Edit_Queue.md"

_HEADER = (
    "# Edit Queue — Brand\n\n"
    "Edit requests triggered from the dashboard's \"new edit\" action. Each line "
    "is a **stub** until the Remotion edit repo (Active_Backlog C1) is wired — no "
    "edit is produced yet.\n\n"
)


def request_edit(video_name: str = "", note: str = "") -> dict:
    """Queue an edit request and return a stubbed (no-op) trigger response."""
    EDITS_PATH.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    label = video_name.strip() or "unassigned"
    detail = note.strip() or "(no note)"
    line = f"- [ ] {ts} · **{label}** · {detail} · _queued — Remotion repo not yet connected_\n"

    existing = EDIT_QUEUE_FILE.read_text(encoding="utf-8") if EDIT_QUEUE_FILE.exists() else _HEADER
    write_md(EDIT_QUEUE_FILE, existing + line)  # .bak-safe Python I/O

    return {
        "ok": True,
        "stubbed": True,
        "video_name": video_name,
        "queued_at": ts,
        "queue_file": str(EDIT_QUEUE_FILE),
        "message": (
            "Edit request queued. The Remotion edit repo isn't connected yet — "
            "this is a stub trigger (no edit produced)."
        ),
    }
