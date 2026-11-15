"""Named Lebensplan scenarios in ``scenarios.json``.

Schema: ``{"version": 1, "scenarios": [{"id", "name", "created", "overrides"}]}``.
``overrides`` are partial inputs on top of the Excel base. Every change reads
the file fresh, edits it, and writes atomically (tmp file + replace); unknown
fields are preserved.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import get_logger

logger = get_logger(__name__)

SCHEMA_VERSION = 1


def _empty() -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "scenarios": []}


def load(path: Path) -> dict[str, Any]:
    """Read the scenario file; a missing file is an empty store."""
    if not path.exists():
        return _empty()
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("version", SCHEMA_VERSION)
    data.setdefault("scenarios", [])
    return data


def _write(path: Path, data: dict[str, Any]) -> None:
    """Atomic write: temp file in the same folder, then replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".scenarios-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _slug(name: str) -> str:
    norm = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-") or "szenario"


def list_scenarios(path: Path) -> list[dict[str, Any]]:
    """All saved scenarios, in file order."""
    return load(path)["scenarios"]


def save_scenario(path: Path, name: str, overrides: dict[str, Any],
                  scenario_id: str | None = None) -> dict[str, Any]:
    """Create a scenario, or replace the overrides of ``scenario_id``.

    Saving under an existing name (without id) overwrites that scenario.
    """
    name = name.strip()
    if not name:
        raise ValueError("Szenario braucht einen Namen")
    data = load(path)
    items = data["scenarios"]
    target = None
    if scenario_id:
        target = next((s for s in items if s.get("id") == scenario_id), None)
        if target is None:
            raise KeyError(scenario_id)
    else:
        target = next((s for s in items if s.get("name") == name), None)
    if target is None:
        existing = {s.get("id") for s in items}
        base = _slug(name)
        sid, n = base, 2
        while sid in existing:
            sid, n = f"{base}-{n}", n + 1
        target = {"id": sid, "created": datetime.now().isoformat(timespec="seconds")}
        items.append(target)
    target["name"] = name
    target["overrides"] = overrides
    target["updated"] = datetime.now().isoformat(timespec="seconds")
    _write(path, data)
    logger.info("lifeplan scenario saved: %s", target["id"])
    return target


def delete_scenario(path: Path, scenario_id: str) -> None:
    """Remove a scenario; KeyError if unknown."""
    data = load(path)
    before = len(data["scenarios"])
    data["scenarios"] = [s for s in data["scenarios"] if s.get("id") != scenario_id]
    if len(data["scenarios"]) == before:
        raise KeyError(scenario_id)
    _write(path, data)
    logger.info("lifeplan scenario deleted: %s", scenario_id)
