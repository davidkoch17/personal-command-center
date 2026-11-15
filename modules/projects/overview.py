"""Project overviews — parse and surgically edit ``_overview.md`` in each project folder.

Every project folder ``1 - Projects/<N> - <Name>/`` carries an ``_overview.md``:
YAML frontmatter (``project``, ``status``, ``updated``, ``next_action``,
``review_by``) plus fixed ``##`` sections recognised by their emoji:

* 🧭 status — free text with "Was gerade läuft" / "Nächste Aktion"
* ✅ open items — ``- [ ]`` / ``- [x]`` grouped under ``**Group**`` lines; ⏳ = waiting
* 🕒 recent activity — ``- **DD.MM.** text`` bullets, newest first
* 📝 notes & decisions — free Markdown
* 📂 where things live — a Markdown table
* 💬 updates — inbox: an HTML comment, then free lines Claude folds in later

David and Claude (chat sessions) maintain these files; the dashboard only reads
them and makes two tiny edits: toggling one checkbox and appending one update
line. Writes re-read the file, change exactly one line (plus ``updated`` in the
frontmatter), save a ``.bak`` first and replace the file atomically — never a
rewrite from a cached copy, because Claude may be editing the same file.

Parsing is forgiving: a missing file, missing sections or extra text yield empty
fields, never an exception.
"""
from __future__ import annotations

import heapq
import logging
import os
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import yaml

from core.config import PROJECTS_PATH, VAULT_PATH

logger = logging.getLogger(__name__)

OVERVIEW_NAME = "_overview.md"
STALE_DAYS = 21
STATUS_ORDER = {"active": 1, "waiting": 2, "paused": 3, "done": 4}

# Patched in tests to point at a temporary projects folder.
PROJECTS_ROOT: Path = PROJECTS_PATH
VAULT_ROOT: Path = VAULT_PATH

_FOLDER_RE = re.compile(r"^(\d+)\s+-\s+(.+)$")
_CHECK_RE = re.compile(r"^(\s*[-*]\s+\[)([ xX])(\]\s?)(.*)$")
_GROUP_RE = re.compile(r"^\*\*(.+?)\*\*\s*(.*)$")
_ACTIVITY_RE = re.compile(r"^\s*[-*]\s+\*\*(.+?)\*\*\s*(.*)$")
_DDMM_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})?")
_LABEL_RE = re.compile(r"\*\*([^*]+?):\*\*\s*(.*)")

SECTION_EMOJI = {
    "🧭": "status",
    "✅": "open",
    "🕒": "activity",
    "📝": "notes",
    "📂": "files",
    "💬": "updates",
}

_SKIP_DIR_NAMES = {"!old", "__pycache__", "node_modules"}
_SKIP_FILE_NAMES = {OVERVIEW_NAME, "_bootstrap.py", ".status.json", "desktop.ini", "thumbs.db"}

_WRITE_LOCK = threading.Lock()


class OverviewError(Exception):
    """A write could not be applied (unknown project, item not found, ...)."""


# --------------------------------------------------------------------------- #
# Locating projects
# --------------------------------------------------------------------------- #
def _project_dirs() -> list[tuple[str, Path]]:
    """``[(id, folder)]`` for every ``<N> - <Name>`` folder, sorted by number."""
    out: list[tuple[str, Path]] = []
    if not PROJECTS_ROOT.exists():
        return out
    for d in PROJECTS_ROOT.iterdir():
        m = _FOLDER_RE.match(d.name)
        if d.is_dir() and m:
            out.append((str(int(m.group(1))), d))
    return sorted(out, key=lambda x: int(x[0]))


def project_dir(project_id: str) -> Path:
    """Resolve ``"3"``, ``"03"``, ``"3 - Project Ulli Acebuche"`` or ``"03_..."`` to a folder.

    Raises ``FileNotFoundError`` if no project folder matches.
    """
    m = re.match(r"^\s*(\d+)", str(project_id))
    if m:
        want = str(int(m.group(1)))
        for pid, d in _project_dirs():
            if pid == want:
                return d
    raise FileNotFoundError(f"No project folder for id {project_id!r}")


def overview_path(project_id: str) -> Path:
    """Path of the project's ``_overview.md`` (may not exist)."""
    return project_dir(project_id) / OVERVIEW_NAME


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def _split_frontmatter(text: str) -> tuple[dict[str, Any], list[str], int]:
    """Return (frontmatter dict, body lines, index of first body line in the file)."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                try:
                    meta = yaml.safe_load("\n".join(lines[1:i])) or {}
                except yaml.YAMLError:
                    logger.warning("unparseable frontmatter in overview; ignoring it")
                    meta = {}
                if not isinstance(meta, dict):
                    meta = {}
                return meta, lines[i + 1:], i + 1
    return {}, lines, 0


def _section_key(heading: str) -> str | None:
    for emoji, key in SECTION_EMOJI.items():
        if emoji in heading:
            return key
    return None


def _sections(lines: list[str], offset: int) -> dict[str, dict[str, Any]]:
    """Map section key -> {"title", "start", "lines": [(file_line_no, text)]}.

    ``start`` is the file line number of the ``##`` heading. A section runs until
    the next ``#``/``##`` heading or a bare ``---`` rule (the footer separator).
    """
    out: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    for i, line in enumerate(lines):
        n = i + offset
        s = line.strip()
        if s.startswith("#"):
            current = None
            if s.startswith("## "):
                key = _section_key(s)
                if key and key not in out:
                    current = {"title": s[3:].strip(), "start": n, "lines": []}
                    out[key] = current
            continue
        if s == "---":
            current = None
            continue
        if current is not None:
            current["lines"].append((n, line))
    return out


def _iso(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    s = str(value).strip()
    try:
        return date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        return None


def _infer_date(raw: str, ref: date) -> str | None:
    """``"15.11."`` -> ISO date. Uses the last DD.MM. in ``raw`` (ranges like
    ``03.–04.10.``); a missing year is the one that puts the date on/before ``ref``."""
    matches = list(_DDMM_RE.finditer(raw))
    if not matches:
        return None
    m = matches[-1]
    day, month = int(m.group(1)), int(m.group(2))
    try:
        if m.group(3):
            year = int(m.group(3))
            year = year + 2000 if year < 100 else year
            return date(year, month, day).isoformat()
        d = date(ref.year, month, day)
        if d > ref + timedelta(days=1):
            d = date(ref.year - 1, month, day)
        return d.isoformat()
    except ValueError:
        return None


def _text(sec: dict[str, Any] | None) -> str:
    if not sec:
        return ""
    return "\n".join(t for _, t in sec["lines"]).strip()


def _parse_status(sec: dict[str, Any] | None) -> dict[str, Any]:
    md = _text(sec)
    current = next_action = None
    for line in md.splitlines():
        m = _LABEL_RE.search(line)
        if not m:
            continue
        label = m.group(1).strip().lower()
        if "läuft" in label or "lauft" in label or "current" in label:
            current = m.group(2).strip()
        elif "nächste" in label or "next" in label:
            next_action = m.group(2).strip()
    return {"markdown": md, "current": current, "next_action": next_action}


def _parse_open(sec: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Checkbox items in file order, each tagged with its group (bold line above)."""
    items: list[dict[str, Any]] = []
    group: str | None = None
    group_note = ""
    if not sec:
        return items
    for n, line in sec["lines"]:
        m = _CHECK_RE.match(line)
        if m:
            text = m.group(4).strip()
            items.append({
                "index": len(items),
                "line": n,
                "text": text,
                "checked": m.group(2) in "xX",
                "waiting": "⏳" in text,
                "group": group,
                "group_note": group_note,
            })
            continue
        g = _GROUP_RE.match(line.strip())
        if g and not line.lstrip().startswith(("- ", "* ")):
            group, group_note = g.group(1).strip(), g.group(2).strip()
    return items


def _parse_activity(sec: dict[str, Any] | None, ref: date) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not sec:
        return out
    for _, line in sec["lines"]:
        m = _ACTIVITY_RE.match(line)
        if m:
            raw = m.group(1).strip()
            out.append({"date_raw": raw, "date": _infer_date(raw, ref), "text": m.group(2).strip()})
        elif line.strip().startswith(("- ", "* ")):
            out.append({"date_raw": "", "date": None, "text": line.strip()[2:].strip()})
    return out


def _parse_table(sec: dict[str, Any] | None, folder: Path | None) -> dict[str, Any]:
    """Markdown table -> {"headers": [...], "rows": [{"cells": [...], "path", "vault_path", "is_dir"}]}."""
    headers: list[str] = []
    rows: list[dict[str, Any]] = []
    extra: list[str] = []
    if not sec:
        return {"headers": headers, "rows": rows, "extra": ""}
    for _, line in sec["lines"]:
        s = line.strip()
        if not s.startswith("|"):
            if s:
                extra.append(s)
            continue
        # Split on unescaped pipes only (Obsidian wikilinks in tables use ``\|``).
        cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s.strip().strip("|"))]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        if not headers:
            headers = cells
            continue
        row: dict[str, Any] = {"cells": cells, "path": None, "vault_path": None, "is_dir": False}
        if folder is not None and cells:
            first = cells[0]
            ticked = re.findall(r"`([^`]+)`", first)
            candidate = (ticked[0] if ticked else first).strip().strip("/")
            if candidate:
                p = folder / candidate
                try:
                    if p.exists():
                        row["path"] = str(p)
                        row["vault_path"] = _vault_rel(p)
                        row["is_dir"] = p.is_dir()
                except OSError:
                    pass
        rows.append(row)
    return {"headers": headers, "rows": rows, "extra": "\n".join(extra)}


def _parse_updates(sec: dict[str, Any] | None) -> list[str]:
    """Free lines under 💬, minus HTML comments and blanks."""
    out: list[str] = []
    if not sec:
        return out
    in_comment = False
    for _, line in sec["lines"]:
        s = line.strip()
        if in_comment:
            if "-->" in s:
                in_comment = False
                s = s.split("-->", 1)[1].strip()
            else:
                continue
        while "<!--" in s:
            before, _, after = s.partition("<!--")
            if "-->" in after:
                s = (before + after.split("-->", 1)[1]).strip()
            else:
                s = before.strip()
                in_comment = True
                break
        if s:
            out.append(s)
    return out


def _vault_rel(p: Path) -> str | None:
    try:
        return p.relative_to(VAULT_ROOT).as_posix()
    except ValueError:
        return None


def parse_overview(text: str, folder: Path | None = None, today: date | None = None) -> dict[str, Any]:
    """Parse an ``_overview.md`` text into its frontmatter + sections. Never raises."""
    meta, body, offset = _split_frontmatter(text or "")
    secs = _sections(body, offset)
    ref = today or date.today()
    status = str(meta.get("status") or "").strip().lower() or None
    return {
        "project": str(meta.get("project")).strip() if meta.get("project") else None,
        "status": status,
        "updated": _iso(meta.get("updated")),
        "next_action": str(meta.get("next_action")).strip() if meta.get("next_action") else None,
        "review_by": _iso(meta.get("review_by")),
        "sections_present": sorted(secs.keys()),
        "status_section": _parse_status(secs.get("status")),
        "open": _parse_open(secs.get("open")),
        "activity": _parse_activity(secs.get("activity"), ref),
        "notes_md": _text(secs.get("notes")),
        "files_table": _parse_table(secs.get("files"), folder),
        "updates": _parse_updates(secs.get("updates")),
        "titles": {k: v["title"] for k, v in secs.items()},
    }


def _read_text(path: Path) -> str:
    """Read preserving line endings (``newline=""``); empty string if missing."""
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


# --------------------------------------------------------------------------- #
# Recent files
# --------------------------------------------------------------------------- #
def _skip_dir(name: str) -> bool:
    low = name.lower()
    return (
        name.startswith(".")
        or name in _SKIP_DIR_NAMES
        or "cacheclip" in low
        or ("davinci" in low and "backup" in low)
        or "resolve project backups" in low
    )


def _skip_file(name: str) -> bool:
    low = name.lower()
    return (
        name.startswith((".", "~$"))
        or name in _SKIP_FILE_NAMES
        or low.endswith(".status.json")
        or ".bak" in low
        or low.endswith(".tmp")
    )


def _iter_files(folder: Path):
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if not _skip_dir(d)]
        for fn in filenames:
            if _skip_file(fn):
                continue
            p = Path(dirpath) / fn
            try:
                st = p.stat()
            except OSError:
                continue
            yield p, st


def recent_files(project_id: str, limit: int = 15) -> list[dict[str, Any]]:
    """Newest files in the project folder: rel path, modified (ISO), size, abs + vault path."""
    try:
        folder = project_dir(project_id)
    except FileNotFoundError:
        return []
    newest = heapq.nlargest(limit, _iter_files(folder), key=lambda x: x[1].st_mtime)
    return [
        {
            "rel_path": p.relative_to(folder).as_posix(),
            "name": p.name,
            "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            "size": st.st_size,
            "path": str(p),
            "vault_path": _vault_rel(p),
        }
        for p, st in newest
    ]


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #
def read_overview(project_id: str, today: date | None = None) -> dict[str, Any]:
    """Full parsed overview for one project. Missing file -> empty sections."""
    folder = project_dir(project_id)
    path = folder / OVERVIEW_NAME
    data = parse_overview(_read_text(path), folder, today)
    m = _FOLDER_RE.match(folder.name)
    data.update({
        "id": str(int(m.group(1))) if m else folder.name,
        "folder": folder.name,
        "name": data["project"] or (m.group(2) if m else folder.name),
        "exists": path.exists(),
        "overview_path": str(path),
        "overview_vault_path": _vault_rel(path),
    })
    return data


def _card(project_id: str, today: date) -> dict[str, Any]:
    ov = read_overview(project_id, today)
    unchecked = [i for i in ov["open"] if not i["checked"]]
    waiting = sum(1 for i in unchecked if i["waiting"])
    last = ov["activity"][0] if ov["activity"] else None
    newest_file = recent_files(project_id, limit=1)
    last_file = newest_file[0]["modified"][:10] if newest_file else None
    dates = [d for d in ((last or {}).get("date"), last_file) if d]
    freshest = max(dates) if dates else None
    stale = freshest is None or date.fromisoformat(freshest) < today - timedelta(days=STALE_DAYS)
    review_due = bool(ov["review_by"] and ov["review_by"] <= today.isoformat())
    return {
        "id": ov["id"],
        "name": ov["name"],
        "folder": ov["folder"],
        "status": ov["status"],
        "next_action": ov["next_action"] or ov["status_section"]["next_action"],
        "updated": ov["updated"],
        "review_by": ov["review_by"],
        "open_count": len(unchecked) - waiting,
        "waiting_count": waiting,
        "last_activity": last,
        "last_file_change": last_file,
        "last_touch": freshest,
        "stale": stale,
        "review_due": review_due,
        "exists": ov["exists"],
    }


def _sort_key(card: dict[str, Any]) -> tuple[int, int, int]:
    return (
        0 if card["review_due"] else 1,
        STATUS_ORDER.get(card["status"] or "", 5),
        int(card["id"]) if str(card["id"]).isdigit() else 999,
    )


def list_projects(today: date | None = None) -> list[dict[str, Any]]:
    """Card data for every project, sorted: review due -> active -> waiting -> paused -> done."""
    ref = today or date.today()
    cards: list[dict[str, Any]] = []
    for pid, _ in _project_dirs():
        try:
            cards.append(_card(pid, ref))
        except Exception:  # one broken project must not take down the grid
            logger.warning("could not build project card for %s", pid, exc_info=True)
    return sorted(cards, key=_sort_key)


# --------------------------------------------------------------------------- #
# Writing (surgical, one line at a time)
# --------------------------------------------------------------------------- #
@dataclass
class _Doc:
    lines: list[str]  # keepends=True
    newline: str


def _load_doc(path: Path) -> _Doc:
    if not path.exists():
        raise OverviewError(f"{path} does not exist")
    text = _read_text(path)
    newline = "\r\n" if "\r\n" in text else "\n"
    return _Doc(text.splitlines(keepends=True), newline)


def _stamp_updated(doc: _Doc, today: date) -> None:
    """Set ``updated:`` inside the frontmatter (insert it if missing)."""
    lines = doc.lines
    if not lines or lines[0].strip() != "---":
        return
    for i in range(1, len(lines)):
        s = lines[i].strip()
        if s == "---":
            lines.insert(i, f"updated: {today.isoformat()}{doc.newline}")
            return
        if re.match(r"^updated\s*:", s):
            ending = lines[i][len(lines[i].rstrip("\r\n")):] or doc.newline
            lines[i] = f"updated: {today.isoformat()}{ending}"
            return


def _write_doc(path: Path, doc: _Doc) -> None:
    """Back up, then atomically replace ``path`` with ``doc``."""
    shutil.copy2(path, path.with_name(path.name + ".bak"))
    fd, tmp = tempfile.mkstemp(prefix=".overview-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write("".join(doc.lines))
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _mutate(project_id: str, fn: Callable[[_Doc, dict[str, Any]], Any], today: date | None) -> Any:
    """Re-read the file, let ``fn`` change one line, stamp ``updated``, write back."""
    ref = today or date.today()
    path = overview_path(project_id)
    with _WRITE_LOCK:
        doc = _load_doc(path)
        parsed = parse_overview("".join(doc.lines), None, ref)
        result = fn(doc, parsed)
        _stamp_updated(doc, ref)
        _write_doc(path, doc)
        return result


def toggle_item(
    project_id: str,
    item: int | str,
    expected_text: str | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Flip one ``- [ ]`` / ``- [x]`` under ✅.

    ``item`` is the 0-based item index or the item's text. With an index plus
    ``expected_text``, the text must still match (else it is looked up by text),
    so a concurrent edit by Claude can never make us tick the wrong line.
    """
    def apply(doc: _Doc, parsed: dict[str, Any]) -> dict[str, Any]:
        items = parsed["open"]
        target = None
        if isinstance(item, int) or (isinstance(item, str) and item.isdigit() and expected_text is not None):
            idx = int(item)
            if 0 <= idx < len(items) and (expected_text is None or items[idx]["text"] == expected_text.strip()):
                target = items[idx]
        text = expected_text if expected_text is not None else (item if isinstance(item, str) else None)
        if target is None and text is not None:
            matches = [i for i in items if i["text"] == text.strip()]
            if len(matches) == 1:
                target = matches[0]
        if target is None:
            raise OverviewError("open item not found (file changed?) — reload and try again")
        n = target["line"]
        m = _CHECK_RE.match(doc.lines[n].rstrip("\r\n"))
        if not m:
            raise OverviewError("line is no longer a checkbox — reload and try again")
        ending = doc.lines[n][len(doc.lines[n].rstrip("\r\n")):]
        new_mark = " " if m.group(2) in "xX" else "x"
        doc.lines[n] = f"{m.group(1)}{new_mark}{m.group(3)}{m.group(4)}{ending}"
        return {"index": target["index"], "text": target["text"], "checked": new_mark == "x"}

    return _mutate(project_id, apply, today)


def append_update(project_id: str, text: str, now: datetime | None = None) -> dict[str, Any]:
    """Insert ``- DD.MM. HH:MM – <text>`` at the end of the 💬 section. Nothing else changes."""
    clean = " ".join((text or "").split())
    if not clean:
        raise OverviewError("update text is empty")
    ts = now or datetime.now()
    entry = f"- {ts:%d.%m. %H:%M} – {clean}"

    def apply(doc: _Doc, parsed: dict[str, Any]) -> dict[str, Any]:
        _, body, offset = _split_frontmatter("".join(doc.lines))
        sec = _sections(body, offset).get("updates")
        nl = doc.newline
        if sec is None:
            # No inbox section yet: add one at the end of the file.
            if doc.lines and not doc.lines[-1].endswith(("\n", "\r")):
                doc.lines[-1] += nl
            doc.lines.extend([nl, f"## 💬 Updates{nl}", f"{entry}{nl}"])
            return {"line": entry}
        last = sec["start"]
        for n, line in sec["lines"]:
            if line.strip():
                last = n
        if not doc.lines[last].endswith(("\n", "\r")):
            doc.lines[last] += nl
        doc.lines.insert(last + 1, f"{entry}{nl}")
        return {"line": entry}

    return _mutate(project_id, apply, ts.date())
