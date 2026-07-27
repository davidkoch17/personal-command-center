"""Cash Flow pillar: ledger-backed income/expense tracking.

David hands raw bank/card statements, receipts, and screenshots directly to
Claude in conversation; Claude parses and appends normalized rows here — there
is no in-app upload flow. This ledger (``cashflow_transactions.jsonl``) is the
source of truth for the Cash Flow pillar's revenue/expense analysis, replacing
the old manual Excel Transactions/Income sheets. Net worth and holdings stay
Excel-sourced (``modules.finance.money``) and are entirely untouched here —
the two domains are deliberately independent.

Storage (repo ``data/`` dir, gitignored, never the vault):
- ``cashflow_transactions.jsonl`` — one JSON entry per line, append-only.
- ``cashflow_reserve_balance.json`` — manual monthly Notgroschen balance snapshot.
- ``cashflow_goal.json`` — David's monthly savings-goal target.
- ``cashflow_budget.json`` — per-category budget targets.

Needs-review convention: when Claude ingests bank/card data on David's behalf
and is genuinely unsure how to categorize or classify a transaction, it should
set ``needs_review=True`` with a specific ``question`` on that entry rather
than guessing — David resolves these in-app via the needs-review queue. This
is for small ongoing uncertainties; a big batch catch-up (e.g. a backlog of
statements) still warrants its own one-off review doc instead.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from core.config import (
    CASHFLOW_BUDGET_FILE,
    CASHFLOW_GOAL_FILE,
    CASHFLOW_INVESTABLE_INCOME_CATEGORIES,
    CASHFLOW_RESERVE_BALANCE_FILE,
    CASHFLOW_TRANSACTIONS_FILE,
    NOTGROSCHEN_TARGET,
    SPLIT_RATIO_TO_RESERVE,
    get_logger,
)

logger = get_logger(__name__)

Direction = Literal["income", "expense"]


class CashflowEntry(BaseModel):
    """A single dated income or expense line."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    date: date
    direction: Direction
    amount: float                      # positive magnitude
    category: str
    account: Optional[str] = None      # e.g. "Haspa Giro", "Amex Gold"
    description: str = ""
    source_file: Optional[str] = None
    notes: Optional[str] = None
    needs_review: bool = False
    question: Optional[str] = None     # why it's flagged, e.g. "Groceries or Dining?"


# --- Ledger (cashflow_transactions.jsonl) ------------------------------------

def _dedupe_key(e: CashflowEntry) -> str:
    """Content hash so re-feeding the same statement twice never double-counts."""
    raw = f"{e.date.isoformat()}|{e.direction}|{e.amount:.2f}|{e.category}|{e.account}|{e.description}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def list_entries() -> list[CashflowEntry]:
    """Every ledger entry, sorted by date ascending."""
    if not CASHFLOW_TRANSACTIONS_FILE.exists():
        return []
    out: list[CashflowEntry] = []
    for line in CASHFLOW_TRANSACTIONS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(CashflowEntry(**json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:  # noqa: BLE001
            logger.warning("Skipping malformed cashflow ledger line: %s", exc)
    return sorted(out, key=lambda e: e.date)


def add_entry(e: CashflowEntry) -> bool:
    """Append one entry. Returns False (no-op) if an identical entry already exists."""
    existing = {_dedupe_key(x) for x in list_entries()}
    if _dedupe_key(e) in existing:
        return False
    CASHFLOW_TRANSACTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = e.model_dump()
    payload["date"] = e.date.isoformat()
    with CASHFLOW_TRANSACTIONS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")
    return True


def add_entries(entries: list[CashflowEntry]) -> dict:
    """Bulk-append with dedup. Returns ``{"added": n, "skipped": n}``."""
    added = skipped = 0
    for e in entries:
        if add_entry(e):
            added += 1
        else:
            skipped += 1
    logger.info("cashflow ledger: +%d entries, %d duplicates skipped", added, skipped)
    return {"added": added, "skipped": skipped}


def _write_all_entries(entries: list[CashflowEntry]) -> None:
    """Rewrite the entire JSONL ledger from ``entries`` (used by :func:`resolve_entry`)."""
    CASHFLOW_TRANSACTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for e in entries:
        payload = e.model_dump()
        payload["date"] = e.date.isoformat()
        lines.append(json.dumps(payload))
    CASHFLOW_TRANSACTIONS_FILE.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def needs_review_entries() -> list[CashflowEntry]:
    """All ledger entries currently flagged for review, sorted by date."""
    return [e for e in list_entries() if e.needs_review]


def resolve_entry(id: str, **fields) -> Optional[CashflowEntry]:
    """Apply an answer to one flagged entry (by ``id``) and clear its review flag.

    ``fields`` overrides the existing row's values (typically built from
    ``CashflowResolveRequest(...).model_dump(exclude_unset=True)``); ``id``
    itself is never overridden, and ``needs_review`` always clears regardless
    of what's passed. Returns the updated entry, or ``None`` if no entry with
    that id exists.
    """
    fields.pop("id", None)
    fields["needs_review"] = False
    entries = list_entries()
    for i, e in enumerate(entries):
        if e.id == id:
            merged = {**e.model_dump(), **fields, "id": id}
            updated = CashflowEntry(**merged)
            entries[i] = updated
            _write_all_entries(entries)
            logger.info("Resolved cashflow entry %s (category=%s)", id, updated.category)
            return updated
    return None


def clear_all() -> int:
    """Delete every ledger entry (e.g. to wipe synthetic test data). Returns count removed."""
    n = len(list_entries())
    if CASHFLOW_TRANSACTIONS_FILE.exists():
        CASHFLOW_TRANSACTIONS_FILE.unlink()
    logger.info("cashflow ledger cleared (%d entries removed)", n)
    return n


def available_months() -> list[str]:
    """Sorted ``YYYY-MM`` months that have at least one ledger entry."""
    return sorted({e.date.strftime("%Y-%m") for e in list_entries()})


def entries_for_month(month: str) -> list[CashflowEntry]:
    return [e for e in list_entries() if e.date.strftime("%Y-%m") == month]


# --- Monthly analytics --------------------------------------------------------

def monthly_income_by_category(month: str) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for e in entries_for_month(month):
        if e.direction == "income":
            totals[e.category] += e.amount
    return {k: round(v, 2) for k, v in totals.items()}


def monthly_expenses_by_category(month: str) -> list[dict]:
    """Expense totals per category for ``month``, sorted descending."""
    totals: dict[str, float] = defaultdict(float)
    for e in entries_for_month(month):
        if e.direction == "expense":
            totals[e.category] += e.amount
    rows = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return [{"category": k, "amount": round(v, 2)} for k, v in rows]


def monthly_transactions(month: str, direction: Optional[Direction] = None) -> list[dict]:
    """All individual entries for ``month``, sorted by date (optionally filtered)."""
    rows = entries_for_month(month)
    if direction:
        rows = [r for r in rows if r.direction == direction]
    rows = sorted(rows, key=lambda e: e.date)
    return [
        {
            "date": e.date.isoformat(),
            "direction": e.direction,
            "description": e.description,
            "amount": round(e.amount, 2),
            "category": e.category,
            "account": e.account or "",
            "notes": e.notes or "",
        }
        for e in rows
    ]


def monthly_summary(month: str) -> dict:
    """Income/expense totals + breakdowns + net + savings rate for ``month``."""
    income_by_cat = monthly_income_by_category(month)
    expenses_by_cat = monthly_expenses_by_category(month)
    income_total = round(sum(income_by_cat.values()), 2)
    expenses_total = round(sum(c["amount"] for c in expenses_by_cat), 2)
    net = round(income_total - expenses_total, 2)
    savings_rate = round(net / income_total, 4) if income_total else None
    return {
        "month": month,
        "income_by_category": income_by_cat,
        "income_total": income_total,
        "expenses_by_category": expenses_by_cat,
        "expenses_total": expenses_total,
        "net": net,
        "savings_rate": savings_rate,
    }


def trend(months: int = 12) -> list[dict]:
    """Last ``months`` of ``{month, income, expenses, savings}`` for the trend chart."""
    window = available_months()[-months:] if months else available_months()
    out = []
    for m in window:
        s = monthly_summary(m)
        out.append({"month": m, "income": s["income_total"], "expenses": s["expenses_total"], "savings": s["net"]})
    return out


def category_trend(months: int = 12) -> list[dict]:
    """Wide rows ``{Month, <category>: amount, ...}`` for the multi-line category chart."""
    window = available_months()[-months:] if months else available_months()
    out = []
    for m in window:
        row: dict = {"Month": m}
        for c in monthly_expenses_by_category(m):
            row[c["category"]] = c["amount"]
        out.append(row)
    return out


# --- Small JSON stores (reserve balance / goal / budget) --------------------

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:  # noqa: BLE001
        logger.warning("%s unreadable: %s", path.name, exc)
        return {}


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# --- Reserve balance (manual Notgroschen snapshot) ---------------------------

def set_reserve_balance(month: str, value: float) -> None:
    data = _load_json(CASHFLOW_RESERVE_BALANCE_FILE)
    data[month] = value
    _save_json(CASHFLOW_RESERVE_BALANCE_FILE, data)
    logger.info("Reserve balance for %s set to %.2f", month, value)


def reserve_status(month: str) -> dict:
    """Latest recorded reserve balance on/before ``month``, vs. the Notgroschen target."""
    data = _load_json(CASHFLOW_RESERVE_BALANCE_FILE)
    months = sorted(m for m in data if m <= month)
    balance = data[months[-1]] if months else None
    percent_filled = round(min(100.0, balance / NOTGROSCHEN_TARGET * 100), 1) if balance is not None else None
    remaining = round(max(0.0, NOTGROSCHEN_TARGET - balance), 2) if balance is not None else None
    return {
        "month": month, "reserve_balance": balance, "target": NOTGROSCHEN_TARGET,
        "percent_filled": percent_filled, "remaining_to_target": remaining,
    }


# --- Savings goal -------------------------------------------------------------

def get_savings_goal() -> Optional[float]:
    return _load_json(CASHFLOW_GOAL_FILE).get("monthly_savings_goal")


def set_savings_goal(value: Optional[float]) -> None:
    data = _load_json(CASHFLOW_GOAL_FILE)
    if value is None:
        data.pop("monthly_savings_goal", None)
    else:
        data["monthly_savings_goal"] = value
    _save_json(CASHFLOW_GOAL_FILE, data)


def goal_progress(month: str) -> dict:
    """This month's net savings vs. the goal target."""
    goal = get_savings_goal()
    actual = monthly_summary(month)["net"]
    percent_of_goal = round(min(150.0, actual / goal * 100), 1) if goal else None
    return {
        "month": month, "goal": goal, "actual_savings": actual,
        "percent_of_goal": percent_of_goal,
        "on_track": (actual >= goal) if goal is not None else None,
    }


# --- Budget targets -------------------------------------------------------

def get_budget() -> dict[str, float]:
    return _load_json(CASHFLOW_BUDGET_FILE)


def set_budget_target(category: str, value: Optional[float]) -> None:
    data = _load_json(CASHFLOW_BUDGET_FILE)
    if value is None:
        data.pop(category, None)
    else:
        data[category] = value
    _save_json(CASHFLOW_BUDGET_FILE, data)


# --- Investable surplus + reserve/invest split (Mehrkontenmodell) -----------

def investable_income(month: str) -> float:
    """Sum of income whose category counts as real earned surplus."""
    by_cat = monthly_income_by_category(month)
    return round(sum(v for c, v in by_cat.items() if c in CASHFLOW_INVESTABLE_INCOME_CATEGORIES), 2)


def investable_surplus(month: str) -> float:
    expenses_total = sum(c["amount"] for c in monthly_expenses_by_category(month))
    return round(investable_income(month) - expenses_total, 2)


def split_recommendation(month: str) -> dict:
    """Waterfall: fill the reserve to target first, then invest the rest.

    Negative or zero surplus routes nothing anywhere (to_reserve = to_invest = 0)
    rather than recommending a "negative" allocation.
    """
    surplus = investable_surplus(month)
    reserve = reserve_status(month)
    balance = reserve["reserve_balance"] or 0.0

    if surplus <= 0:
        to_reserve, to_invest = 0.0, 0.0
    elif balance < NOTGROSCHEN_TARGET:
        to_reserve = round(min(surplus * SPLIT_RATIO_TO_RESERVE, NOTGROSCHEN_TARGET - balance), 2)
        to_invest = round(surplus - to_reserve, 2)
    else:
        to_reserve, to_invest = 0.0, round(surplus, 2)

    income_total = investable_income(month)
    savings_rate = round(surplus / income_total, 4) if income_total else None

    return {
        "month": month, "surplus": surplus, "to_reserve": to_reserve, "to_invest": to_invest,
        "reserve": reserve, "savings_rate": savings_rate,
    }
