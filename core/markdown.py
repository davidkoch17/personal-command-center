"""Parser helpers for the conventional structures in David's Obsidian vault.

All functions are defensive: malformed or missing input yields empty results
rather than exceptions. Line indices are computed against ``md.split("\\n")`` so
that :func:`toggle_task` can target the exact same lines a parser reported.
"""
from __future__ import annotations

import re
from datetime import date

# Checkbox bullet, e.g. "- [ ] text" or "  - [x] text".
_TASK_RE = re.compile(r"^(\s*)-\s\[([ xX])\]\s?(.*)$")
# Level-1/2 heading, used to delimit sections.
_SECTION_BREAK_RE = re.compile(r"^#{1,2}\s")
# Project heading, e.g. "## 01_Thesis_MA_Synergies 🟢".
_PROJECT_RE = re.compile(r"^##\s+(\d{2})_(.+?)(?:\s+([\U0001F7E2\U0001F7E1\U0001F534]))?\s*$")

# Emoji -> (label, hex color). Done is detected from status text, not emoji.
_STATUS_BY_EMOJI = {
    "\U0001F7E2": ("ON TRACK", "#10B981"),
    "\U0001F7E1": ("NEEDS ATTENTION", "#F59E0B"),
    "\U0001F534": ("AT RISK", "#EF4444"),
}
_STATUS_DONE = ("DONE", "#9CA3AF")
_STATUS_UNKNOWN = ("", "#9CA3AF")


def _heading_text(line: str) -> str | None:
    """Return the text of a level-2 heading line, or None if not a `## ` heading."""
    if line.startswith("## "):
        return line[3:].strip()
    return None


def parse_section_bullets(md: str, header: str) -> list[dict]:
    """Return the checkbox bullets under the ``## {header}`` section.

    An exact (case-insensitive) heading match wins; failing that, the first
    heading that starts with ``header`` is used. So ``header="This weekend"``
    matches ``## This weekend (30-31 May) — high priority`` by prefix, while
    ``header="This week"`` matches the literal ``## This week`` section rather
    than being swallowed by the longer "weekend" heading.

    Only ``- [ ]`` and ``- [x]`` lines are returned, each as
    ``{"text": str, "checked": bool, "raw": str, "line_index": int}``. The
    ``line_index`` is the 0-based index into ``md.split("\\n")``.

    Returns an empty list if the section or its bullets are absent.
    """
    if not md or not header:
        return []
    target = header.strip().lower()
    lines = md.split("\n")

    # Locate the section start: prefer an exact heading match, else first prefix.
    exact_start: int | None = None
    prefix_start: int | None = None
    for i, line in enumerate(lines):
        heading = _heading_text(line)
        if heading is None:
            continue
        hl = heading.lower()
        if hl == target:
            exact_start = i
            break
        if prefix_start is None and hl.startswith(target):
            prefix_start = i
    start = exact_start if exact_start is not None else prefix_start
    if start is None:
        return []

    bullets: list[dict] = []
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if _SECTION_BREAK_RE.match(line):
            break  # next level-1/2 heading ends the section
        m = _TASK_RE.match(line)
        if m:
            bullets.append(
                {
                    "text": m.group(3).strip(),
                    "checked": m.group(2).lower() == "x",
                    "raw": line,
                    "line_index": i,
                }
            )
    return bullets


# Any list bullet with an OPTIONAL checkbox. Group 2 is the checkbox state
# (" "/"x"/"X") or None for a plain bullet; group 3 is the bullet text.
_ANY_BULLET_RE = re.compile(r"^(\s*)-\s+(?:\[([ xX])\]\s*)?(.*)$")
# A bold-led "hard date" bullet: "- **Wed 3 June (evening):** Dinner in FFM".
# The em-dash (—) and hyphen are accepted as separators after the bold.
_HARD_DATE_BULLET_RE = re.compile(r"^\s*-\s*\*\*([^*]+?)\*\*[:\s—-]+(.+)$")


def _section_start(lines: list[str], header: str) -> int | None:
    """Index of the ``## {header}`` heading: exact match wins, else first prefix.

    Mirrors the matching rules documented on :func:`parse_section_bullets` so
    every section-scoped parser locates the same heading.
    """
    target = header.strip().lower()
    prefix_start: int | None = None
    for i, line in enumerate(lines):
        heading = _heading_text(line)
        if heading is None:
            continue
        hl = heading.lower()
        if hl == target:
            return i
        if prefix_start is None and hl.startswith(target):
            prefix_start = i
    return prefix_start


def parse_section_lines(md: str, header: str) -> list[dict]:
    """Return *all* bullet lines under ``## {header}`` — checkbox or plain.

    Unlike :func:`parse_section_bullets` (which only returns ``- [ ]``/``- [x]``
    items), this also captures plain bullets such as
    ``- **Mon 8 June:** Defense``. That is how the "Next week" preview section is
    written: dated notes rather than actionable checkboxes. Each item carries an
    ``is_task`` flag — True when the bullet had a checkbox, False for a plain
    note — so the UI can render previews read-only.

    Section matching mirrors :func:`parse_section_bullets`. Each item is
    ``{"text", "checked", "is_task", "raw", "line_index"}``. Empty bullets are
    skipped; returns an empty list if the section is absent.
    """
    if not md or not header:
        return []
    lines = md.split("\n")
    start = _section_start(lines, header)
    if start is None:
        return []
    out: list[dict] = []
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if _SECTION_BREAK_RE.match(line):
            break
        m = _ANY_BULLET_RE.match(line)
        if not m:
            continue
        text = m.group(3).strip()
        if not text:
            continue
        state = m.group(2)
        out.append(
            {
                "text": text,
                "checked": (state or "").lower() == "x",
                "is_task": state is not None,
                "raw": line,
                "line_index": i,
            }
        )
    return out


def parse_hard_dates(md: str) -> list[dict]:
    """Find a "Hard dates" subsection in a task file and parse its bullets.

    Scans for the first line containing "hard dates" (case-insensitive), then
    reads the following bold-led bullets until the next ``## `` heading::

        - **Wed 3 June (evening):** Dinner in FFM — book train tickets
        - **2026-06-05:** Credit cards due

    Returns ``[{"date": date | None, "label": str, "raw": str}, ...]`` sorted by
    date ascending (undated items last). Defensive: missing/garbled input yields
    an empty list.
    """
    out: list[dict] = []
    if not md:
        return out
    in_section = False
    for line in md.split("\n"):
        if not in_section:
            if re.search(r"hard dates", line, re.IGNORECASE):
                in_section = True
            continue
        if line.startswith("## "):  # next section ends the hard-dates block
            break
        m = _HARD_DATE_BULLET_RE.match(line)
        if not m:
            continue
        date_str = m.group(1).strip().rstrip(":").strip()
        out.append(
            {
                "date": _parse_date_loose(date_str),
                "label": m.group(2).strip(),
                "raw": date_str,
            }
        )
    out.sort(key=lambda d: d["date"] or date.max)
    return out


# Month names: English + German, keyed by the lowercased first few letters.
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    "janu": 1, "febr": 2, "märz": 3, "marz": 3, "mai": 5, "juni": 6, "juli": 7,
    "okto": 10, "deze": 12,
}


def _parse_date_loose(s: str) -> date | None:
    """Parse a loose date string: ISO first, then "Day Month [Year]" patterns.

    Handles ``2026-06-05``, ``Wed 3 June``, ``3 June 2026``, ``Mon 8 June`` and
    German month names. Parenthetical qualifiers (e.g. ``(evening)``) are
    stripped. Returns None if no date can be recovered.
    """
    s = re.sub(r"\s*\(.+?\)\s*", "", s).strip()
    try:
        return date.fromisoformat(s)
    except ValueError:
        pass
    m = re.search(r"(\d{1,2})\s+([A-Za-zäöü]+)(?:\s+(\d{4}))?", s)
    if not m:
        return None
    day = int(m.group(1))
    name = m.group(2).lower()
    month = _MONTHS.get(name) or _MONTHS.get(name[:4]) or _MONTHS.get(name[:3])
    if not month:
        return None
    year = int(m.group(3)) if m.group(3) else date.today().year
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _bullet_value(lines: list[str], label: str) -> str:
    """Return text following a `- **{label}:**` bullet within the given lines."""
    pat = re.compile(r"^\s*-\s+\*\*" + re.escape(label) + r":?\*\*:?\s*(.*)$", re.IGNORECASE)
    for line in lines:
        m = pat.match(line)
        if m:
            return m.group(1).strip()
    return ""


def parse_projects(md: str) -> list[dict]:
    """Parse ``Project_Index.md`` into a list of project dicts.

    Each ``## NN_Name <emoji>`` section with a recognised RAG emoji becomes
    ``{"id", "name", "folder", "status_emoji", "status_text", "next_step",
    "folder_link"}``. ``name`` is the folder suffix with emoji stripped (e.g.
    ``Thesis_MA_Synergies``); ``folder`` is ``NN_name``. Sections without a RAG
    emoji (e.g. the Ideen pipeline or Areas) are skipped.

    Returns an empty list on malformed input.
    """
    if not md:
        return []
    lines = md.split("\n")
    # Find indices of project headings.
    heads: list[tuple[int, re.Match]] = []
    for i, line in enumerate(lines):
        m = _PROJECT_RE.match(line)
        if m and m.group(3):  # require a RAG emoji to count as a project
            heads.append((i, m))
    projects: list[dict] = []
    for idx, (start, m) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        # Stop the section at the first level-1 break (e.g. a "---" separator
        # followed by other content is fine; we just scan to next project head).
        body = lines[start + 1 : end]
        pid, name, emoji = m.group(1), m.group(2).strip(), m.group(3)
        folder_link = ""
        for line in body:
            lm = re.search(r"\[\[(.+?)\]\]", line)
            if lm and "folder" in line.lower():
                folder_link = lm.group(1)
                break
        projects.append(
            {
                "id": pid,
                "name": name,
                "folder": f"{pid}_{name}",
                "status_emoji": emoji,
                "status_text": _bullet_value(body, "Status"),
                "next_step": _bullet_value(body, "Next step"),
                "folder_link": folder_link,
            }
        )
    return projects


def status_display(project: dict) -> tuple[str, str]:
    """Map a project dict to ``(label, hex_color)`` for a colored status line.

    "Done" detected in the status text overrides the RAG emoji and renders grey.
    """
    status_text = (project.get("status_text") or "").lower()
    if "done" in status_text:
        return _STATUS_DONE
    return _STATUS_BY_EMOJI.get(project.get("status_emoji"), _STATUS_UNKNOWN)


def parse_reading_list(md: str) -> dict[str, list[str]]:
    """Parse ``Reading_List.md`` into ``{to_read, reading_now, done}``.

    Each item is the bullet text after the checkbox (markdown preserved). Only
    the three canonical sections are read; other sections (e.g. "Classics to
    confirm") are ignored. Returns empty lists on malformed input.
    """
    buckets: dict[str, list[str]] = {"to_read": [], "reading_now": [], "done": []}
    if not md:
        return buckets
    header_map = {"to read": "to_read", "reading now": "reading_now", "done": "done"}
    lines = md.split("\n")
    current: str | None = None
    for line in lines:
        heading = _heading_text(line)
        if heading is not None:
            current = header_map.get(heading.lower())
            continue
        if current is None:
            continue
        m = _TASK_RE.match(line)
        if m:
            text = m.group(3).strip()
            if text:
                buckets[current].append(text)
    return buckets


def add_task_to_section(md: str, section: str, text: str) -> str:
    """Insert ``- [ ] {text}`` directly under the first matching section heading.

    The section is matched by case-insensitive prefix against ``## `` headings,
    so ``section="This week"`` finds ``## This week`` and ``section="This weekend"``
    finds ``## This weekend (30-31 May)``. The new bullet is inserted immediately
    after the heading line. Returns the markdown unchanged if ``md``/``section``/
    ``text`` is empty or the section is absent.

    Mirrors the insertion behaviour of the Inbox "convert to task" flow so the
    REST API and the Streamlit dashboard write identically.
    """
    if not md or not section or not text:
        return md
    lines = md.split("\n")
    target = section.strip().lower()
    for i, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip().lower().startswith(target):
            lines.insert(i + 1, f"- [ ] {text.strip()}")
            return "\n".join(lines)
    return md


def toggle_task(md: str, line_index: int) -> tuple[str, bool]:
    """Toggle the ``[ ]``/``[x]`` checkbox on a specific line.

    Returns ``(new_md, new_state)`` where ``new_state`` is True if the task is
    now checked. If the target line is out of range or not a checkbox, the
    markdown is returned unchanged with ``new_state=False``.
    """
    if not md:
        return md, False
    lines = md.split("\n")
    if not (0 <= line_index < len(lines)):
        return md, False
    m = _TASK_RE.match(lines[line_index])
    if not m:
        return md, False
    indent, state, text = m.group(1), m.group(2), m.group(3)
    new_checked = state.lower() != "x"
    box = "x" if new_checked else " "
    lines[line_index] = f"{indent}- [{box}] {text}"
    return "\n".join(lines), new_checked
