"""Career checklists: onboarding admin + technicals refresh tracker (Phase 9b).

Both are simple Markdown checkbox files in ``3_Career/05_Current_Job/``. Toggles
write back via Python file I/O (the vault writer keeps a ``.bak``). Files are
created from defaults on first save.

Also surfaces two read-only views for the Career page: recent activity in
``3_Career/`` and the status of the Evercore 3-statement model (a Cowork build
that lands as an Excel file in ``05_Current_Job/``).
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from core import vault
from core.config import CAREER_PATH

CURRENT_JOB_DIR = CAREER_PATH / "05_Current_Job"
ONBOARDING_FILE = CURRENT_JOB_DIR / "Onboarding.md"
TECHNICALS_FILE = CURRENT_JOB_DIR / "Technicals_Tracker.md"

# --- 3-statement model -------------------------------------------------------
# The model is built in Cowork and saved as an Excel workbook in the current-job
# folder. We detect any spreadsheet there whose name reads like a 3-statement
# model; ``MODEL_EXPECTED`` is the canonical path we tell David to save it to.
MODEL_EXPECTED = CURRENT_JOB_DIR / "3_Statement_Model.xlsx"
_MODEL_NAME_RE = re.compile(r"(3[\s_-]*statement|three[\s_-]*statement|3sm|3[\s_-]*stmt)", re.I)
_MODEL_SUFFIXES = {".xlsx", ".xlsm", ".xls"}

# Files/folders to skip when surfacing recent activity.
_ACTIVITY_SKIP_SUFFIXES = {".bak"}
_ACTIVITY_SKIP_DIR_PREFIXES = (".", "_archive")

DEFAULT_ONBOARDING = [
    "FFM address registered (Anmeldung)",
    "GKV / health insurance elected",
    "BU (Berufsunfähigkeit) policy in place",
    "Employment contract signed & filed",
    "Equipment / IT setup confirmed",
    "Bank details submitted to payroll",
]

TECHNICALS_MODULES = [
    "DCF",
    "LBO",
    "M&A accretion / dilution",
    "Trading comps",
    "Precedent transactions",
    "Sector primers",
]


def parse_checklist(md: str) -> list[dict]:
    """Parse ``- [ ]`` / ``- [x]`` lines into ``[{text, checked}]``."""
    items = []
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("- [ ] "):
            items.append({"text": s[6:].strip(), "checked": False})
        elif s.lower().startswith("- [x] "):
            items.append({"text": s[6:].strip(), "checked": True})
    return items


def build_checklist_md(title: str, items: list[dict]) -> str:
    lines = [f"# {title}", ""]
    for it in items:
        box = "x" if it["checked"] else " "
        lines.append(f"- [{box}] {it['text']}")
    return "\n".join(lines) + "\n"


def _read_or_default(path, title: str, defaults: list[str]) -> list[dict]:
    md = vault.read_md(path)
    if md:
        items = parse_checklist(md)
        if items:
            return items
    return [{"text": t, "checked": False} for t in defaults]


def read_onboarding() -> list[dict]:
    return _read_or_default(ONBOARDING_FILE, "Onboarding admin", DEFAULT_ONBOARDING)


def save_onboarding(items: list[dict]) -> None:
    vault.write_md(ONBOARDING_FILE, build_checklist_md("Onboarding admin", items))


def read_technicals() -> list[dict]:
    return _read_or_default(TECHNICALS_FILE, "Technicals refresh tracker", TECHNICALS_MODULES)


def save_technicals(items: list[dict]) -> None:
    vault.write_md(TECHNICALS_FILE, build_checklist_md("Technicals refresh tracker", items))


def _rel(path: Path) -> str:
    """Vault-relative POSIX path, for the OS-open / link endpoints."""
    return path.relative_to(CAREER_PATH.parent).as_posix()


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def recent_activity(limit: int = 8) -> list[dict]:
    """Most-recently-modified files anywhere under ``3_Career/``.

    Skips backups and archive/hidden folders. Returns newest first as
    ``[{name, rel_path, folder, modified}]`` — ``folder`` is the parent
    relative to ``3_Career/`` (e.g. ``05_Current_Job``).
    """
    if not CAREER_PATH.exists():
        return []
    rows: list[dict] = []
    for p in CAREER_PATH.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in _ACTIVITY_SKIP_SUFFIXES:
            continue
        rel_parts = p.relative_to(CAREER_PATH).parts
        if any(part.startswith(_ACTIVITY_SKIP_DIR_PREFIXES) for part in rel_parts[:-1]):
            continue
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        folder = "/".join(rel_parts[:-1]) or "."
        rows.append({
            "name": p.name,
            "rel_path": _rel(p),
            "folder": folder,
            "modified": _iso(mtime),
            "_mtime": mtime,
        })
    rows.sort(key=lambda r: r["_mtime"], reverse=True)
    for r in rows:
        del r["_mtime"]
    return rows[:limit]


def model_status() -> dict:
    """Status of the Evercore 3-statement model (a Cowork-built Excel workbook).

    Scans ``05_Current_Job/`` for a spreadsheet whose name reads like a
    3-statement model and reports the newest match. ``status`` is ``ready`` when
    one exists, else ``not_started``; ``expected_path`` is where to save it.
    """
    expected_rel = _rel(MODEL_EXPECTED)
    match: Path | None = None
    if CURRENT_JOB_DIR.exists():
        candidates = [
            p for p in CURRENT_JOB_DIR.rglob("*")
            if p.is_file()
            and p.suffix.lower() in _MODEL_SUFFIXES
            and _MODEL_NAME_RE.search(p.stem)
        ]
        if candidates:
            match = max(candidates, key=lambda p: p.stat().st_mtime)
    if match is None:
        return {
            "status": "not_started",
            "found": False,
            "path": None,
            "name": None,
            "last_modified": None,
            "expected_path": expected_rel,
            "note": "Build in Cowork, then save to the expected path so it shows here.",
        }
    return {
        "status": "ready",
        "found": True,
        "path": _rel(match),
        "name": match.name,
        "last_modified": _iso(match.stat().st_mtime),
        "expected_path": expected_rel,
        "note": "Detected a 3-statement model in 05_Current_Job.",
    }
