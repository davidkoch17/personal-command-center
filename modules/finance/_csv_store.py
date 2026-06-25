"""Tiny CSV upsert/append helpers for the Phase B finance data files.

All Phase B series (``positions_daily.csv``, ``networth_daily.csv``,
``expenses.csv`` …) are flat CSVs in the repo's ``data/`` dir (NOT the vault),
written exclusively through these helpers so behaviour stays consistent:

- :func:`read_rows` — load a CSV into a list of ``dict`` (``[]`` if absent).
- :func:`write_rows` — overwrite with a fixed column order.
- :func:`upsert_rows` — replace rows matching a composite key, keep the rest.
  This is what makes the daily snapshot **idempotent**: re-running for the same
  date overwrites that date's rows instead of appending duplicates.

Pure stdlib ``csv`` (no pandas dependency for the write path) so the scheduled
snapshot job stays lightweight. All values are written as strings; callers coerce
on read.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Sequence

from core.config import get_logger

logger = get_logger(__name__)


def read_rows(path: Path) -> list[dict]:
    """Read a CSV into a list of dicts (empty list if the file does not exist)."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_rows(path: Path, rows: Iterable[dict], columns: Sequence[str]) -> None:
    """Overwrite ``path`` with ``rows`` using ``columns`` as the header order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: _fmt(row.get(c)) for c in columns})


def append_rows(path: Path, rows: Iterable[dict], columns: Sequence[str]) -> None:
    """Append ``rows`` to ``path`` (writing the header first if the file is new)."""
    rows = list(rows)
    if not rows:
        return
    existing = read_rows(path)
    write_rows(path, existing + rows, columns)


def upsert_rows(
    path: Path,
    rows: Iterable[dict],
    columns: Sequence[str],
    key_cols: Sequence[str],
) -> int:
    """Replace existing rows whose ``key_cols`` match an incoming row; keep the rest.

    Returns the number of incoming rows written. Existing rows not superseded are
    preserved. The merged result is re-sorted by the key columns and rewritten in
    full — fine for these small daily series (one row/position/day).
    """
    rows = list(rows)
    if not rows:
        return 0
    incoming_keys = {_key(r, key_cols) for r in rows}
    kept = [r for r in read_rows(path) if _key(r, key_cols) not in incoming_keys]
    merged = kept + [{c: r.get(c) for c in columns} for r in rows]
    merged.sort(key=lambda r: tuple(str(r.get(k, "")) for k in key_cols))
    write_rows(path, merged, columns)
    return len(rows)


def _key(row: dict, key_cols: Sequence[str]) -> tuple:
    return tuple(str(row.get(k, "")) for k in key_cols)


def _fmt(value) -> str:
    """Render a cell value as a string (empty string for ``None``)."""
    if value is None:
        return ""
    return str(value)
