"""SQLite store for captures — the source of truth (screenshots/audio = backup).

Schema is built exactly to the v3 build spec § b. SQLite (not CSV) is used
because captures need filtering, status mutation, and a capture->many-tickers
relation. The DB lives in the repo's ``data/`` dir (not OneDrive) and is created
on first use.

All access goes through a short-lived connection per call with ``row_factory``
set to :class:`sqlite3.Row`, so callers get dict-like rows and never hold a lock
across the slow OCR/Whisper/Claude steps.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from core.config import CAPTURES_DB, DATA_DIR, get_logger

logger = get_logger(__name__)


# --- DDL, verbatim to the spec § b ------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS captures (
  id TEXT PRIMARY KEY,
  captured_at TEXT,
  type TEXT,                               -- image | voice
  topic_tag TEXT,
  topic_slug TEXT,
  ocr_text TEXT,
  voice_transcript TEXT,
  source_hint TEXT,
  ai_tags TEXT,                            -- json array
  routing_suggestions TEXT,                -- json
  routing_locked INTEGER DEFAULT 0,
  category TEXT,                           -- news | task | park | note
  status TEXT DEFAULT 'pending',           -- pending | approved-auto | approved | archived
  image_path TEXT,
  voice_path TEXT,
  notes TEXT,
  processed_at TEXT
);

CREATE TABLE IF NOT EXISTS capture_tickers (
  capture_id TEXT,
  ticker TEXT,
  sector TEXT,
  PRIMARY KEY (capture_id, ticker)
);

CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY,
  text TEXT,
  project TEXT,
  status TEXT DEFAULT 'open',
  source_capture_id TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS notes (
  id INTEGER PRIMARY KEY,
  title TEXT,
  body TEXT,
  ai_tags TEXT,
  source_capture_id TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS park_queue (
  id INTEGER PRIMARY KEY,
  title TEXT,
  body TEXT,
  source_capture_id TEXT,
  status TEXT DEFAULT 'pending',
  created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_captures_status ON captures(status);
CREATE INDEX IF NOT EXISTS idx_captures_category ON captures(category);
CREATE INDEX IF NOT EXISTS idx_capture_tickers_ticker ON capture_tickers(ticker);
"""


@contextmanager
def connect(db_path: Path = CAPTURES_DB) -> Iterator[sqlite3.Connection]:
    """Yield a connection with the schema ensured and rows as dicts.

    ``WAL`` mode lets the watcher write while the dashboard reads. The schema is
    created on every connect (all statements are ``IF NOT EXISTS``), so the DB
    self-heals if the file was deleted.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path = CAPTURES_DB) -> None:
    """Create the DB + schema if absent (idempotent)."""
    with connect(db_path):
        pass
    logger.info("captures DB ready at %s", db_path)


def capture_exists(capture_id: str, db_path: Path = CAPTURES_DB) -> bool:
    """True if a capture with this ``id`` is already ingested (idempotency key)."""
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM captures WHERE id = ?", (capture_id,)
        ).fetchone()
    return row is not None


def existing_ids(db_path: Path = CAPTURES_DB) -> set[str]:
    """Return the set of all ingested capture ids (one query per poll)."""
    with connect(db_path) as conn:
        rows = conn.execute("SELECT id FROM captures").fetchall()
    return {r["id"] for r in rows}


def insert_capture(record: dict, tickers: list[dict], db_path: Path = CAPTURES_DB) -> None:
    """Insert a capture row plus its ticker links in one transaction.

    ``record`` keys map 1:1 to the ``captures`` columns; ``ai_tags`` and
    ``routing_suggestions`` are JSON-encoded here if passed as Python objects.
    ``tickers`` is a list of ``{"ticker": str, "sector": str|None}`` dicts.
    """
    rec = dict(record)
    for json_col in ("ai_tags", "routing_suggestions"):
        val = rec.get(json_col)
        if val is not None and not isinstance(val, str):
            rec[json_col] = json.dumps(val, ensure_ascii=False)
    rec.setdefault("processed_at", datetime.now().isoformat())
    cols = [
        "id", "captured_at", "type", "topic_tag", "topic_slug", "ocr_text",
        "voice_transcript", "source_hint", "ai_tags", "routing_suggestions",
        "routing_locked", "category", "status", "image_path", "voice_path",
        "notes", "processed_at",
    ]
    placeholders = ", ".join("?" for _ in cols)
    values = [rec.get(c) for c in cols]
    with connect(db_path) as conn:
        conn.execute(
            f"INSERT INTO captures ({', '.join(cols)}) VALUES ({placeholders})",
            values,
        )
        for t in tickers:
            ticker = (t.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO capture_tickers (capture_id, ticker, sector) "
                "VALUES (?, ?, ?)",
                (rec["id"], ticker, t.get("sector")),
            )


def insert_note(title: str, body: str, ai_tags: list[str] | str | None,
                source_capture_id: str, db_path: Path = CAPTURES_DB) -> int:
    """Append a row to ``notes`` (Note captures auto-file here). Returns row id."""
    tags = ai_tags if isinstance(ai_tags, str) or ai_tags is None else json.dumps(
        ai_tags, ensure_ascii=False
    )
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO notes (title, body, ai_tags, source_capture_id, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (title, body, tags, source_capture_id, datetime.now().isoformat()),
        )
        return int(cur.lastrowid)


def insert_task(text: str, project: str | None, source_capture_id: str,
                db_path: Path = CAPTURES_DB) -> int:
    """Append a row to ``tasks`` (used at approval time, not on capture)."""
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO tasks (text, project, status, source_capture_id, created_at) "
            "VALUES (?, ?, 'open', ?, ?)",
            (text, project, source_capture_id, datetime.now().isoformat()),
        )
        return int(cur.lastrowid)


def insert_park(title: str, body: str, source_capture_id: str,
                db_path: Path = CAPTURES_DB) -> int:
    """Append a row to ``park_queue`` (used at approval time, not on capture)."""
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO park_queue (title, body, source_capture_id, status, created_at) "
            "VALUES (?, ?, ?, 'pending', ?)",
            (title, body, source_capture_id, datetime.now().isoformat()),
        )
        return int(cur.lastrowid)


# --- read side (Phase D — News Captures Hub + Connected News) ----------------
# Statuses (spec § b approval model B): pending | approved-auto | approved | archived.
# Categories: news | task | park | note.

# Sentinel: lets update_capture() distinguish "set routing to null" from "leave unchanged".
_UNSET = object()


def _row_to_capture(row: sqlite3.Row) -> dict:
    """Materialize a captures row into a dict, decoding the JSON columns."""
    rec = dict(row)
    for json_col in ("ai_tags", "routing_suggestions"):
        raw = rec.get(json_col)
        if isinstance(raw, str) and raw.strip():
            try:
                rec[json_col] = json.loads(raw)
            except json.JSONDecodeError:
                rec[json_col] = raw
        elif raw is None:
            rec[json_col] = [] if json_col == "ai_tags" else None
    return rec


def _tickers_for(conn: sqlite3.Connection, capture_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT ticker, sector FROM capture_tickers WHERE capture_id = ? ORDER BY ticker",
        (capture_id,),
    ).fetchall()
    return [{"ticker": r["ticker"], "sector": r["sector"]} for r in rows]


def list_captures(status: str | None = None, category: str | None = None,
                  limit: int = 300, db_path: Path = CAPTURES_DB) -> list[dict]:
    """Captures newest-first, optionally filtered by status/category, with tickers."""
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if category:
        clauses.append("category = ?")
        params.append(category)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM captures {where} ORDER BY captured_at DESC LIMIT ?", params
        ).fetchall()
        out = []
        for r in rows:
            rec = _row_to_capture(r)
            rec["tickers"] = _tickers_for(conn, rec["id"])
            out.append(rec)
    return out


def get_capture(capture_id: str, db_path: Path = CAPTURES_DB) -> dict | None:
    """One capture with its ticker links (None if not found)."""
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM captures WHERE id = ?", (capture_id,)).fetchone()
        if row is None:
            return None
        rec = _row_to_capture(row)
        rec["tickers"] = _tickers_for(conn, capture_id)
    return rec


def captures_for_ticker(ticker: str, exclude_archived: bool = True,
                        db_path: Path = CAPTURES_DB) -> list[dict]:
    """All captures linked to ``ticker`` (Connected News), newest first."""
    tk = (ticker or "").strip().upper()
    if not tk:
        return []
    archived = "" if not exclude_archived else "AND c.status != 'archived'"
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""SELECT c.*, ct.sector AS link_sector
                 FROM captures c JOIN capture_tickers ct ON ct.capture_id = c.id
                 WHERE ct.ticker = ? {archived}
                 ORDER BY c.captured_at DESC""",
            (tk,),
        ).fetchall()
        out = []
        for r in rows:
            rec = _row_to_capture(r)
            rec["link_sector"] = r["link_sector"]
            rec["tickers"] = _tickers_for(conn, rec["id"])
            out.append(rec)
    return out


def sector_radar(exclude_archived: bool = True, db_path: Path = CAPTURES_DB) -> list[dict]:
    """Capture counts grouped by sector (the watchlist-wide 'what changed' radar)."""
    archived = "WHERE c.status != 'archived'" if exclude_archived else ""
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""SELECT COALESCE(NULLIF(ct.sector, ''), 'Uncategorized') AS sector,
                       COUNT(DISTINCT ct.capture_id) AS n
                 FROM capture_tickers ct JOIN captures c ON c.id = ct.capture_id
                 {archived}
                 GROUP BY sector ORDER BY n DESC""",
        ).fetchall()
    return [{"sector": r["sector"], "count": r["n"]} for r in rows]


def ticker_counts(exclude_archived: bool = True, db_path: Path = CAPTURES_DB) -> dict[str, int]:
    """``{ticker: capture_count}`` for the watchlist Connected-News badges."""
    archived = "WHERE c.status != 'archived'" if exclude_archived else ""
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""SELECT ct.ticker AS ticker, COUNT(DISTINCT ct.capture_id) AS n
                 FROM capture_tickers ct JOIN captures c ON c.id = ct.capture_id
                 {archived}
                 GROUP BY ct.ticker""",
        ).fetchall()
    return {r["ticker"]: r["n"] for r in rows}


def update_capture(capture_id: str, *, status: str | None = None,
                   category: str | None = None,
                   routing_suggestions: object = _UNSET,
                   notes: str | None = None, routing_locked: int | None = None,
                   db_path: Path = CAPTURES_DB) -> bool:
    """Patch mutable capture fields (status/category/routing/notes). True if a row changed."""
    sets, params = [], []
    if status is not None:
        sets.append("status = ?"); params.append(status)
    if category is not None:
        sets.append("category = ?"); params.append(category)
    if routing_suggestions is not _UNSET:
        val = routing_suggestions
        if val is not None and not isinstance(val, str):
            val = json.dumps(val, ensure_ascii=False)
        sets.append("routing_suggestions = ?"); params.append(val)
    if notes is not None:
        sets.append("notes = ?"); params.append(notes)
    if routing_locked is not None:
        sets.append("routing_locked = ?"); params.append(int(routing_locked))
    if not sets:
        return False
    params.append(capture_id)
    with connect(db_path) as conn:
        cur = conn.execute(f"UPDATE captures SET {', '.join(sets)} WHERE id = ?", params)
        return cur.rowcount > 0


def replace_tickers(capture_id: str, tickers: list[dict], db_path: Path = CAPTURES_DB) -> None:
    """Replace the ticker links for a capture (used when David edits routing)."""
    with connect(db_path) as conn:
        conn.execute("DELETE FROM capture_tickers WHERE capture_id = ?", (capture_id,))
        for t in tickers:
            ticker = (t.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO capture_tickers (capture_id, ticker, sector) VALUES (?, ?, ?)",
                (capture_id, ticker, t.get("sector")),
            )


def open_tasks_by_project(db_path: Path = CAPTURES_DB) -> dict[str, list[str]]:
    """``{project_label: [open task texts, newest first]}`` for the Projects pillar.

    Tasks carry the project label the voice classifier writes (one of the known
    projects: ``K&E`` · ``Ulli/Acebuche`` · ``Immos`` · ``Personal Brand``). The
    pillar's ``ProjectCard`` uses this for a live open-task count + top task per
    project. Tasks with no project (or a closed status) are excluded.
    """
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT project, text FROM tasks "
            "WHERE status = 'open' AND project IS NOT NULL AND TRIM(project) != '' "
            "ORDER BY created_at DESC"
        ).fetchall()
    out: dict[str, list[str]] = {}
    for r in rows:
        out.setdefault(r["project"], []).append(r["text"])
    return out


def status_counts(db_path: Path = CAPTURES_DB) -> dict[str, int]:
    """``{status: count}`` across all captures (drives the Captures tab filter chips)."""
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT COALESCE(status, 'pending') AS status, COUNT(*) AS n FROM captures GROUP BY status"
        ).fetchall()
    return {r["status"]: r["n"] for r in rows}
