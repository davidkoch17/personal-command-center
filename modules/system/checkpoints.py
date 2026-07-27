"""Checkpoint log — durable "we are here" markers for the whole app.

Recorded whenever a period is reconciled and closed out (e.g. "July 2026
close"), so any future session — human or Claude — can immediately answer
"where did we leave off" without re-deriving it from the ledgers.

Each call to :func:`record_checkpoint` writes to two places:
- ``data/checkpoints.jsonl`` — machine-readable, append-only, read back by
  ``GET /api/system/checkpoints`` and the Settings page status line.
- ``99_System/Command_Center_Checkpoints.md`` — human-readable, vault-native
  (visible in Obsidian), newest entry first. Written via
  :func:`core.vault.write_md`, which backs up the prior version first, per
  the vault write rules in CLAUDE.md.

Saving a matching Claude Code memory entry is a separate, deliberate step
the operator takes when a checkpoint is recorded — not automated here.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from core import vault
from core.config import CHECKPOINTS_FILE, CHECKPOINTS_NOTE, get_logger

logger = get_logger(__name__)

_NOTE_HEADER = (
    "# Command Center — Checkpoints\n\n"
    "Durable markers of reconciled/closed periods, recorded by the app. "
    "Newest first.\n"
)


def list_checkpoints() -> list[dict]:
    """Every recorded checkpoint, most recent first."""
    if not CHECKPOINTS_FILE.exists():
        return []
    out: list[dict] = []
    for line in CHECKPOINTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:  # noqa: BLE001
            logger.warning("Skipping malformed checkpoint line: %s", exc)
    return sorted(out, key=lambda c: c["timestamp"], reverse=True)


def latest_checkpoint() -> Optional[dict]:
    checkpoints = list_checkpoints()
    return checkpoints[0] if checkpoints else None


def _append_vault_note(entry: dict) -> None:
    """Insert the entry right before the first existing ``## `` heading (i.e.
    newest-first, below the intro paragraph) — or at the end if this is the
    first entry."""
    existing = vault.read_md(CHECKPOINTS_NOTE)
    if not existing.strip():
        existing = _NOTE_HEADER
    section = (
        f"\n## {entry['label']} — {entry['timestamp']}\n\n"
        f"{entry['notes']}\n\n"
        f"```json\n{json.dumps(entry['snapshot'], indent=2)}\n```\n"
    )
    marker = "\n## "
    idx = existing.find(marker)
    if idx == -1:
        updated = existing.rstrip("\n") + "\n" + section
    else:
        updated = existing[:idx] + section + existing[idx:]
    vault.write_md(CHECKPOINTS_NOTE, updated)


def record_checkpoint(label: str, notes: str, snapshot: dict) -> dict:
    """Record a new checkpoint: append to the JSONL log and the vault note.

    ``snapshot`` is any JSON-serializable dict capturing whatever state is
    worth freezing at this point (e.g. that month's cash-flow summary,
    current portfolio holdings) — kept free-form since what matters varies
    per checkpoint.
    """
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "label": label,
        "notes": notes,
        "snapshot": snapshot,
    }
    CHECKPOINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CHECKPOINTS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    _append_vault_note(entry)
    logger.info("Recorded checkpoint: %s", label)
    return entry
