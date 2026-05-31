"""Per-project workspace helpers."""
from pathlib import Path
from datetime import datetime
import shutil
from core.config import PROJECTS_PATH


PRIORITY_EXTENSIONS = [".docx", ".pptx", ".xlsx", ".md", ".pdf"]
EXCLUDE_DIRS = {"_archive", "9_Archive", "Archive", "_drafts"}


def project_root(project_id: str) -> Path:
    """Return the project folder by ID prefix (e.g. '01' -> 1_Projects/01_Thesis...)"""
    for d in sorted(PROJECTS_PATH.iterdir()):
        if d.is_dir() and d.name.startswith(project_id + "_"):
            return d
    raise FileNotFoundError(f"No project with prefix {project_id}")


def list_subfolders(project_id: str) -> list[Path]:
    root = project_root(project_id)
    return sorted([d for d in root.iterdir() if d.is_dir() and d.name not in EXCLUDE_DIRS])


def most_recent_draft(project_id: str) -> Path | None:
    """The most recently modified prioritized-extension file in the project (excluding archives)."""
    root = project_root(project_id)
    candidates = []
    for ext in PRIORITY_EXTENSIONS:
        for p in root.rglob(f"*{ext}"):
            if any(part in EXCLUDE_DIRS for part in p.parts):
                continue
            if p.name.startswith("~$"):  # Office lockfiles
                continue
            candidates.append(p)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def key_files(project_id: str, limit: int = 5) -> list[Path]:
    """Top N recently modified prioritized files."""
    root = project_root(project_id)
    candidates = []
    for ext in PRIORITY_EXTENSIONS:
        for p in root.rglob(f"*{ext}"):
            if any(part in EXCLUDE_DIRS for part in p.parts):
                continue
            if p.name.startswith("~$"):
                continue
            candidates.append(p)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[:limit]


def append_project_log(project_id: str, note: str) -> Path:
    """Append a timestamped note to the project's Project_Log.md."""
    root = project_root(project_id)
    log = root / "Project_Log.md"
    if log.exists():
        backup = log.with_suffix(".md.bak")
        shutil.copy2(log, backup)
        existing = log.read_text(encoding="utf-8")
    else:
        existing = f"# Project Log — {root.name}\n\n"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## {ts}\n\n{note}\n"
    log.write_text(existing + entry, encoding="utf-8")
    return log


def list_drafts(project_id: str) -> list[dict]:
    """Drafts pending send — outgoing letters/emails staged in <project>/Drafts/."""
    root = project_root(project_id)
    drafts_dir = root / "Drafts"
    if not drafts_dir.exists():
        return []
    out = []
    for f in sorted(drafts_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = f.read_text(encoding="utf-8")
        is_sent = text.startswith("---\nstatus: sent")
        out.append({
            "name": f.stem,
            "path": str(f),
            "is_sent": is_sent,
            "modified": datetime.fromtimestamp(f.stat().st_mtime),
        })
    return out
