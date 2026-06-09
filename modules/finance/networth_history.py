"""Monthly net-worth snapshot store (v2 N1 — Wealth-page trend line).

The Wealth page headline shows total net worth *over time*. Two sources feed it:

1. **Authoritative backbone** — the manually-maintained ``Net_Worth`` sheet in
   ``Finance_Tracker.xlsx``. David records a monthly total there; that history is
   the spine of the trend.
2. **Live snapshots** — captured on each finance refresh (the
   ``/api/money/snapshot`` call records the *currently computed* net worth). These
   are deduped to one entry per calendar month, so the store keeps exactly one
   value per month and the current month stays fresh between manual sheet edits.

Cadence (resolves the spec's open "snapshot cadence" decision): **snapshot on
each finance refresh, deduped per month**. A refresh re-writes the current
month's entry in place — cheap and idempotent, no unbounded growth.

The store is a small JSON file in the repo's ``data/`` dir (per-machine, never
the vault, gitignored alongside the other generated finance data).
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

from core.config import DATA_DIR, get_logger

logger = get_logger(__name__)

NETWORTH_STORE = DATA_DIR / "networth_snapshots.json"

_MONTH_RE = re.compile(r"^\d{4}-\d{2}")


def _load() -> list[dict]:
    """Load stored snapshots (``[]`` if the file is absent or unreadable)."""
    if not NETWORTH_STORE.exists():
        return []
    try:
        data = json.loads(NETWORTH_STORE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:  # noqa: BLE001
        logger.warning("net-worth store unreadable (%s); starting empty", exc)
        return []


def _save(records: list[dict]) -> None:
    """Persist snapshots, sorted by month."""
    records = sorted(records, key=lambda r: str(r.get("month", "")))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    NETWORTH_STORE.write_text(json.dumps(records, indent=2), encoding="utf-8")


def record_snapshot(total: float | None, *, components: dict | None = None,
                    source: str = "auto") -> None:
    """Record the current computed net worth, deduped to one entry per month.

    Called on each finance refresh. A missing/zero total is ignored (we never
    overwrite a real month with a blank). The current month's entry is replaced
    in place so the store holds exactly one value per ``YYYY-MM``.
    """
    if total is None:
        return
    try:
        total = float(total)
    except (TypeError, ValueError):
        return
    if total == 0:
        return

    today = date.today()
    month = f"{today.year:04d}-{today.month:02d}"
    records = [r for r in _load() if r.get("month") != month]
    entry: dict = {
        "month": month,
        "date": today.isoformat(),
        "total": round(total, 2),
        "source": source,
    }
    if components:
        entry["components"] = {
            k: (round(float(v), 2) if isinstance(v, (int, float)) else v)
            for k, v in components.items()
            if v is not None
        }
    records.append(entry)
    try:
        _save(records)
    except OSError as exc:  # noqa: BLE001 — a store write must never break a refresh
        logger.warning("could not persist net-worth snapshot: %s", exc)


def _sheet_history() -> dict[str, float]:
    """Monthly totals from the Net_Worth sheet, keyed by ``YYYY-MM``."""
    try:
        from modules.finance.loader import net_worth

        nw = net_worth()
    except Exception as exc:  # noqa: BLE001 — Excel may be missing/locked
        logger.warning("net-worth sheet unavailable: %s", exc)
        return {}
    if nw.empty or "Total Net Worth (€)" not in nw.columns or "Month" not in nw.columns:
        return {}
    out: dict[str, float] = {}
    for _, row in nw.iterrows():
        month = str(row.get("Month") or "").strip()
        total = row.get("Total Net Worth (€)")
        if _MONTH_RE.match(month) and pd.notna(total):
            try:
                out[month[:7]] = float(total)
            except (TypeError, ValueError):
                continue
    return out


def history() -> list[dict]:
    """Merged monthly net-worth series for the trend line.

    The manually-maintained sheet provides the backbone; live snapshots overlay
    it (the dashboard's computed value wins for any month it has captured, so the
    current month reflects live prices). Returns ``[{month, total, source}]``
    sorted ascending by month.
    """
    merged: dict[str, dict] = {
        month: {"month": month, "total": round(total, 2), "source": "sheet"}
        for month, total in _sheet_history().items()
    }
    for rec in _load():
        month = rec.get("month")
        if not month:
            continue
        merged[month] = {
            "month": month,
            "total": rec.get("total"),
            "source": rec.get("source", "auto"),
        }
    return [merged[m] for m in sorted(merged)]
