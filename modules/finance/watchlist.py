"""Watchlist — single source of truth is the vault ``Watchlist.md``.

As of Phase 16 the watchlist universe lives entirely in
``4_Areas/Investing/Watchlist.md`` (the same file the Market Researcher agent
reads), parsed into a tier + theme-section structure. The dashboard reads and
appends to that markdown directly so the agent and the UI can never drift.

The legacy repo-local ``data/watchlist.json`` store (``load``/``add``/``_save``)
is **DEPRECATED** — kept only as a one-time migration source
(:func:`migrate_json_to_md`). New writes must go through :func:`append_entry`.

Vault-write rule: appends go through :func:`core.vault.write_md`, which saves a
``.bak`` first and uses plain Python file I/O (never the Edit/Write tool) — the
OneDrive-safe path required for any file under ``David_Work_OS``.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from core import vault
from core.config import WATCHLIST_FILE, WATCHLIST_UNIVERSE_FILE

logger = logging.getLogger(__name__)

# The single source of truth.
MD_FILE = WATCHLIST_UNIVERSE_FILE

# Canonical ticker pattern — identical to the one watchlist_analytics uses, so
# the agent's universe and the dashboard's universe are guaranteed to match:
# (NKE), (^GSPC), (BTC-USD), (EURUSD=X), (ADS.DE), (P911.DE).
TICKER_RE = re.compile(r"\(([A-Z0-9.\-^]+(?:=[A-Z]+)?)\)")

# Status label derived from the tier (the MD universe has no per-name status).
_TIER_STATUS = {"Tier 1": "macro", "Tier 2": "held", "Tier 3": "watch"}

# Heading: friendly title kept after an em-dash/hyphen, e.g.
# "## Tier 1 — Macro pulse (always monitored)".
_TIER_HEADING_RE = re.compile(r"^##\s+(Tier\s+[123])\b\s*[—\-:]?\s*(.*)$", re.IGNORECASE)
# Tier-3 theme subsection: "### A. US Mega-cap tech (...)". The letter is optional
# so a letter-less "### Ad-hoc (dashboard additions)" still parses.
_SECTION_HEADING_RE = re.compile(r"^###\s+(?:([A-Za-z])\.\s*)?(.+?)\s*$")
# Any other level-2 heading ends the tiered universe ("## Themes", "## Free data sources").
_ANY_H2_RE = re.compile(r"^##\s+(.*)$")

# Where new ad-hoc names land if no explicit section is chosen.
_ADHOC_KEY = "adhoc"
_ADHOC_HEADING = "### Ad-hoc (dashboard additions)"


def _parse_bullet(line: str) -> dict | None:
    """Parse a ``- ...`` bullet into an entry dict, or None if not a bullet.

    Takes the FIRST parenthesised symbol as the ticker (so "Circle (CRCL) — …
    (USDC)" resolves to CRCL, not USDC). Bullets with no ticker symbol — cross
    references like "(Bitcoin in Tier 1)" and topic notes like "**Tom Lee** …" —
    come back with ``ticker=""`` and ``is_ticker=False`` so the UI can show them
    as muted notes rather than clickable cards.
    """
    text = line.strip()
    if not text.startswith("- "):
        return None
    text = text[2:].strip()
    if not text:
        return None
    # Bold-led bullets are topic/annotation notes ("**Huawei** — …", "**Tom Lee**
    # …"), never ticker rows — even when their prose mentions "(QCOM)". Real ticker
    # rows follow the plain "Name (TICKER)" convention with no leading bold.
    m = None if text.startswith("**") else TICKER_RE.search(text)
    if not m:
        clean = re.sub(r"\*+", "", text).strip()
        return {"ticker": "", "name": clean, "notes": "", "is_ticker": False}
    ticker = m.group(1)
    name = re.sub(r"\*+", "", text[: m.start()]).strip()
    notes = re.sub(r"^[—\-:\s]+", "", text[m.end():]).strip()
    return {"ticker": ticker, "name": name, "notes": notes, "is_ticker": True}


def parse_watchlist_md(path: Path = MD_FILE) -> dict:
    """Parse ``Watchlist.md`` into an ordered tier + theme-section structure.

    Returns ``{"sections": [...], "count": int, "tickers": [...]}`` where each
    section is ``{"key", "tier", "letter", "title", "entries": [entry, ...]}``.
    ``count`` and ``tickers`` cover only real (parenthesised) tickers, de-duped
    in first-seen order. Collection stops at the first non-Tier ``##`` heading
    (the "Themes" / "Free data sources" prose blocks carry no tickers).
    """
    md = vault.read_md(path)
    sections: list[dict] = []
    current: dict | None = None
    tier: str | None = None
    collecting = False  # True only inside Tier 1/2/3

    def _new_section(key: str, tier_: str, letter: str, title: str) -> dict:
        sec = {"key": key, "tier": tier_, "letter": letter, "title": title, "entries": []}
        sections.append(sec)
        return sec

    for line in md.split("\n"):
        tier_m = _TIER_HEADING_RE.match(line)
        if tier_m:
            tier = re.sub(r"\s+", " ", tier_m.group(1)).title()  # normalise "Tier 1"
            title = tier_m.group(2).strip()
            collecting = True
            if tier in ("Tier 1", "Tier 2"):
                # These tiers hold bullets directly (no theme subsections).
                current = _new_section(tier.lower().replace(" ", ""), tier, "", title)
            else:
                # Tier 3 entries live under ### subsections; no direct bullets.
                current = None
            continue

        if collecting and line.startswith("### "):
            sec_m = _SECTION_HEADING_RE.match(line)
            if sec_m:
                letter = (sec_m.group(1) or "").upper()
                title = sec_m.group(2).strip()
                key = letter or _slug(title)
                current = _new_section(key, tier or "Tier 3", letter, title)
            continue

        if line.startswith("## "):
            # A non-Tier level-2 heading ends the tiered universe.
            if not _TIER_HEADING_RE.match(line):
                collecting = False
                current = None
            continue

        if collecting and current is not None and line.strip().startswith("- "):
            entry = _parse_bullet(line)
            if entry:
                entry["tier"] = current["tier"]
                entry["section"] = current["key"]
                entry["section_title"] = current["title"]
                entry["letter"] = current["letter"]
                entry["status"] = _TIER_STATUS.get(current["tier"], "")
                current["entries"].append(entry)

    # De-dupe tickers in first-seen order for the count / universe list.
    seen: dict[str, None] = {}
    for sec in sections:
        for e in sec["entries"]:
            if e["is_ticker"]:
                seen.setdefault(e["ticker"], None)
    return {"sections": sections, "count": len(seen), "tickers": list(seen.keys())}


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "section"


def flat_entries(path: Path = MD_FILE) -> list[dict]:
    """All ticker entries across every section (skips non-ticker notes)."""
    data = parse_watchlist_md(path)
    return [e for sec in data["sections"] for e in sec["entries"] if e["is_ticker"]]


def universe(path: Path = MD_FILE) -> list[str]:
    """All unique tickers — the agent's universe, sourced from the same file."""
    return parse_watchlist_md(path)["tickers"]


def form_sections(path: Path = MD_FILE) -> list[dict]:
    """``[{key, label}]`` of append targets for the add-to-watchlist form.

    Lists every existing section plus a default "Ad-hoc" target (first in the
    list) so a quick add lands somewhere sensible without a choice.
    """
    out = [{"key": _ADHOC_KEY, "label": "Tier 3 · Ad-hoc (dashboard additions)"}]
    for sec in parse_watchlist_md(path)["sections"]:
        prefix = f"{sec['letter']}. " if sec["letter"] else ""
        out.append({"key": sec["key"], "label": f"{sec['tier']} · {prefix}{sec['title']}"})
    return out


def _insert_bullet(lines: list[str], heading_idx: int, bullet: str) -> None:
    """Insert ``bullet`` after the last existing bullet in a section, in place."""
    end = len(lines)
    for i in range(heading_idx + 1, len(lines)):
        if re.match(r"^#{2,3}\s", lines[i]):
            end = i
            break
    insert_at = heading_idx + 1
    for i in range(end - 1, heading_idx, -1):
        if lines[i].strip().startswith("- "):
            insert_at = i + 1
            break
    lines.insert(insert_at, bullet)


def append_entry(
    ticker: str,
    name: str = "",
    notes: str = "",
    section_key: str = _ADHOC_KEY,
    path: Path = MD_FILE,
) -> dict:
    """Append a ``- Name (TICKER) — notes`` bullet to ``Watchlist.md``.

    Writes through :func:`core.vault.write_md` (``.bak`` + Python I/O). The
    target section is matched by ``section_key`` (a tier key like ``tier1``, a
    Tier-3 letter like ``"D"``, or ``"adhoc"``). The Ad-hoc section is created
    just before the "Themes" block on first use. A ticker already anywhere in the
    file is a no-op (``{"ok": False, "reason": "already present"}``).
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("Ticker is required.")

    data = parse_watchlist_md(path)
    if ticker in data["tickers"]:
        return {"ok": False, "ticker": ticker, "reason": "already present"}

    bullet = f"- {name.strip() or ticker} ({ticker})"
    if notes.strip():
        bullet += f" — {notes.strip()}"

    md = vault.read_md(path)
    lines = md.split("\n")

    # Resolve the target heading line index.
    target_idx: int | None = None
    if section_key and section_key != _ADHOC_KEY:
        want = section_key.strip().lower()
        for i, line in enumerate(lines):
            tier_m = _TIER_HEADING_RE.match(line)
            if tier_m and re.sub(r"\s+", " ", tier_m.group(1)).title().lower().replace(" ", "") == want:
                target_idx = i
                break
            sec_m = line.startswith("### ") and _SECTION_HEADING_RE.match(line)
            if sec_m:
                letter = (sec_m.group(1) or "").upper()
                if letter and letter.lower() == want:
                    target_idx = i
                    break

    if target_idx is None:
        # Ad-hoc (or an unmatched key): find/create the Ad-hoc section.
        for i, line in enumerate(lines):
            if line.startswith("### ") and "ad-hoc" in line.lower():
                target_idx = i
                break
        if target_idx is None:
            # Create it just before the first non-Tier "## " heading (end of Tier 3).
            insert_block_at = len(lines)
            seen_tier = False
            for i, line in enumerate(lines):
                if _TIER_HEADING_RE.match(line):
                    seen_tier = True
                elif seen_tier and _ANY_H2_RE.match(line):
                    insert_block_at = i
                    break
            block = ["", _ADHOC_HEADING, bullet, ""]
            lines[insert_block_at:insert_block_at] = block
            vault.write_md(path, "\n".join(lines))
            logger.info("Watchlist: created Ad-hoc section and added %s", ticker)
            return {"ok": True, "ticker": ticker, "section": _ADHOC_KEY, "created_section": True}

    _insert_bullet(lines, target_idx, bullet)
    vault.write_md(path, "\n".join(lines))
    logger.info("Watchlist: appended %s under section idx %d", ticker, target_idx)
    return {"ok": True, "ticker": ticker, "section": section_key or _ADHOC_KEY}


def migrate_json_to_md(path: Path = MD_FILE) -> dict:
    """One-time import: copy any unique ``data/watchlist.json`` names into MD.

    Names already present in ``Watchlist.md`` are skipped, so this is idempotent.
    Returns ``{"added": [...], "skipped": [...]}``.
    """
    existing = set(parse_watchlist_md(path)["tickers"])
    added, skipped = [], []
    for it in _load_json():
        tk = str(it.get("ticker", "")).strip().upper()
        if not tk:
            continue
        if tk in existing:
            skipped.append(tk)
            continue
        append_entry(tk, it.get("name", ""), it.get("notes", ""), _ADHOC_KEY, path)
        existing.add(tk)
        added.append(tk)
    logger.info("Watchlist migrate: added=%s skipped=%s", added, skipped)
    return {"added": added, "skipped": skipped}


# ---------------------------------------------------------------------------
# DEPRECATED — legacy data/watchlist.json store. Retained only so
# migrate_json_to_md() can lift any old entries into the markdown source of
# truth. Do not use for new reads/writes.
# ---------------------------------------------------------------------------
VALID_STATUSES = ["researching", "considering", "paused", "exited"]

SEED: list[dict] = [
    {"ticker": "NKE", "name": "Nike", "status": "researching", "notes": "research pending"},
]


def _load_json(path: Path = WATCHLIST_FILE) -> list[dict]:
    """DEPRECATED: load legacy JSON watchlist items (migration source only)."""
    if not path.exists():
        return list(SEED)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        logger.warning("watchlist.json is not a list; ignoring.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read %s: %s", path, exc)
    return list(SEED)


def load(path: Path = WATCHLIST_FILE) -> list[dict]:
    """DEPRECATED alias for the legacy JSON loader. Use parse_watchlist_md()."""
    logger.warning("watchlist.load() is deprecated; Watchlist.md is the source of truth.")
    return _load_json(path)
