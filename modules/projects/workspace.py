"""Per-project workspace helpers."""
import re
from pathlib import Path
from datetime import datetime
import shutil
from core.config import PROJECTS_PATH, VAULT_PATH


PRIORITY_EXTENSIONS = [".docx", ".pptx", ".xlsx", ".md", ".pdf"]
EXCLUDE_DIRS = {"_archive", "9_Archive", "Archive", "_drafts"}

# A milestone bullet: "- YYYY-MM-DD (optional day note): text" — the parenthetical
# and the separator (":", "-", "—") are all optional/flexible.
_MILESTONE_RE = re.compile(
    r"^\s*-\s*(\d{4}-\d{2}-\d{2})\s*(?:\([^)]*\))?\s*[:\-—]?\s*(.*)$"
)
# A list bullet, optionally a checkbox: "- text", "- [ ] text", "- [x] text".
_BULLET_RE = re.compile(r"^(\s*)-\s+(\[[ xX]\]\s*)?(.*\S)\s*$")


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


# ---------------------------------------------------------------------------
# README section parsing (Phase 9a — Milestones / Next Steps / Key Files)
#
# Each active project's README defines three David-curated sections. These are
# read at render time by the Projects overview and the project workspace. All
# parsers are defensive: a missing section yields an empty list.
# ---------------------------------------------------------------------------
def _section_bounds(lines: list[str], header: str) -> tuple[int, int] | None:
    """Return (start, end) line indices for the body under ``## {header}``.

    ``start`` is the first body line (after the heading); ``end`` is exclusive,
    stopping at the next level-1/2 heading. Matching is case-insensitive on the
    heading text. Returns None if the section is absent.
    """
    target = header.strip().lower()
    start = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("## ") and s[3:].strip().lower() == target:
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if re.match(r"^#{1,2}\s", lines[j]):
            end = j
            break
    return start, end


def parse_milestones(readme_text: str) -> list[dict]:
    """Extract the ``## Milestones`` section bullets.

    Each bullet is expected as ``- YYYY-MM-DD[ (note)][: ]text``. Returns
    ``[{"date": "YYYY-MM-DD" | None, "text": str}, ...]`` in file order. Bullets
    without a leading ISO date are kept with ``date=None``; pure-note bullets
    (starting with "(") are skipped.
    """
    if not readme_text:
        return []
    lines = readme_text.split("\n")
    bounds = _section_bounds(lines, "Milestones")
    if not bounds:
        return []
    out: list[dict] = []
    for ln in lines[bounds[0]:bounds[1]]:
        m = _MILESTONE_RE.match(ln)
        if m:
            out.append({"date": m.group(1), "text": m.group(2).strip()})
            continue
        b = _BULLET_RE.match(ln)
        if b and not b.group(3).startswith("("):
            out.append({"date": None, "text": b.group(3).strip()})
    return out


def parse_next_steps(readme_text: str) -> list[dict]:
    """Extract the ``## Next Steps`` section bullets.

    Returns ``[{"text": str, "checked": bool, "line_index": int}, ...]``. Plain
    bullets count as unchecked; ``- [x]`` bullets as checked. ``line_index`` is
    the 0-based index into ``readme_text.split("\\n")`` — the exact line
    :func:`toggle_next_step` rewrites.
    """
    if not readme_text:
        return []
    lines = readme_text.split("\n")
    bounds = _section_bounds(lines, "Next Steps")
    if not bounds:
        return []
    out: list[dict] = []
    for i in range(bounds[0], bounds[1]):
        b = _BULLET_RE.match(lines[i])
        if not b:
            continue
        text = b.group(3).strip()
        if text.startswith("("):  # placeholder note, not a real step
            continue
        checked = bool(b.group(2)) and "x" in b.group(2).lower()
        out.append({"text": text, "checked": checked, "line_index": i})
    return out


def parse_key_files(readme_text: str, project_root: Path) -> list[Path]:
    """Extract the ``## Key Files`` section paths (David-defined, not auto-detected).

    Paths may be backtick-wrapped and are followed by an optional ``— description``.
    They are resolved against the vault root first (the README writes vault-relative
    paths like ``1_Projects/01_.../draft.docx``), then the project root, then taken
    as-is. Pure-note bullets (e.g. "(none yet)") are skipped. The returned Paths may
    not exist — callers render a "missing" state in that case.
    """
    if not readme_text:
        return []
    lines = readme_text.split("\n")
    bounds = _section_bounds(lines, "Key Files")
    if not bounds:
        return []
    out: list[Path] = []
    for ln in lines[bounds[0]:bounds[1]]:
        b = _BULLET_RE.match(ln)
        if not b:
            continue
        body = b.group(3).strip()
        if body.startswith("("):  # placeholder note
            continue
        tick = re.search(r"`([^`]+)`", body)
        raw = tick.group(1).strip() if tick else re.split(r"\s+[—-]\s+", body)[0].strip()
        if not raw:
            continue
        p = Path(raw)
        if p.is_absolute():
            out.append(p)
            continue
        candidates = [VAULT_PATH / raw, project_root / raw]
        chosen = next((c for c in candidates if c.exists()), candidates[0])
        out.append(chosen)
    return out


def _backup(path: Path) -> None:
    """Save a ``.bak`` copy of a vault file before writing (per repo I/O rules)."""
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))


def toggle_next_step(project_id: str, line_index: int) -> bool | None:
    """Toggle the checkbox on a Next Steps bullet in the project's README.

    A plain bullet becomes ``- [x] text``; a checked bullet becomes ``- [ ] text``.
    Writes via Python file I/O with a ``.bak`` backup (OneDrive-safe per repo
    rules). Returns the new checked state, or None if the line isn't a bullet.
    """
    root = project_root(project_id)
    readme = root / "README.md"
    if not readme.exists():
        return None
    text = readme.read_text(encoding="utf-8")
    lines = text.split("\n")
    if not (0 <= line_index < len(lines)):
        return None
    b = _BULLET_RE.match(lines[line_index])
    if not b:
        return None
    indent, box, rest = b.group(1), b.group(2), b.group(3).strip()
    currently_checked = bool(box) and "x" in box.lower()
    new_checked = not currently_checked
    lines[line_index] = f"{indent}- [{'x' if new_checked else ' '}] {rest}"
    _backup(readme)
    readme.write_text("\n".join(lines), encoding="utf-8")
    return new_checked


def add_next_step(project_id: str, text: str) -> None:
    """Append a new bullet to the ``## Next Steps`` section of the README.

    Creates the section at the end of the file if it does not exist. Writes via
    Python file I/O with a ``.bak`` backup.
    """
    text = (text or "").strip()
    if not text:
        return
    root = project_root(project_id)
    readme = root / "README.md"
    existing = readme.read_text(encoding="utf-8") if readme.exists() else f"# {root.name}\n"
    lines = existing.split("\n")
    bounds = _section_bounds(lines, "Next Steps")
    new_bullet = f"- {text}"
    if bounds is None:
        # Append a fresh section.
        suffix = "" if existing.endswith("\n") else "\n"
        existing = existing + f"{suffix}\n## Next Steps\n{new_bullet}\n"
    else:
        # Insert after the last non-empty body line of the section.
        insert_at = bounds[1]
        while insert_at > bounds[0] and not lines[insert_at - 1].strip():
            insert_at -= 1
        lines.insert(insert_at, new_bullet)
        existing = "\n".join(lines)
    _backup(readme)
    readme.write_text(existing, encoding="utf-8")


def create_project(name: str, flow: str, seed: str = "") -> Path:
    """Create a new project folder under ``1_Projects/`` with a seeded README.

    ``name`` is the human name (spaces become underscores). ``flow`` is "Flow A"
    (business venture) or "Flow B" (personal/decision). The next free ``NN_`` index
    is chosen. The README is seeded with the three required sections. Returns the
    created project folder. Does not modify ``Project_Index.md`` — David adds the
    RAG-status entry there during the Weekly Review.
    """
    safe = "".join(c if c.isalnum() or c in " _-&" else "" for c in name).strip()
    safe = re.sub(r"\s+", "_", safe) or "Untitled"
    # Next free 2-digit index among existing NN_ folders.
    used = set()
    for d in PROJECTS_PATH.iterdir():
        if d.is_dir() and len(d.name) >= 2 and d.name[:2].isdigit():
            used.add(int(d.name[:2]))
    nn = 1
    while nn in used:
        nn += 1
    folder = PROJECTS_PATH / f"{nn:02d}_{safe}"
    folder.mkdir(parents=True, exist_ok=False)
    readme = folder / "README.md"
    seed_block = f"\n{seed.strip()}\n" if seed.strip() else "\n"
    readme.write_text(
        f"# {name}\n\n"
        f"**Type:** {flow}\n"
        f"**Created:** {datetime.now():%Y-%m-%d}\n\n"
        f"## Goal\n{seed_block}\n"
        f"## Milestones\n- \n\n"
        f"## Next Steps\n- \n\n"
        f"## Key Files\n- (none yet)\n",
        encoding="utf-8",
    )
    return folder
