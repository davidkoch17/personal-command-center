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
statements) still warrants its own one-off review doc instead. Set
``question_type`` explicitly to tell the frontend whether to render a
category dropdown (``"category"``) or a free-text field (``"freetext"``,
the default) — don't rely on how ``question`` is phrased.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from core.config import (
    CASHFLOW_ACCOUNTS_FILE,
    CASHFLOW_ALERT_CATEGORY_SPIKE_MULTIPLIER,
    CASHFLOW_ALERT_RESERVE_NEAR_FULL,
    CASHFLOW_ALERT_RUNWAY_MONTHS,
    CASHFLOW_BUDGET_FILE,
    CASHFLOW_EXCLUDE_FROM_PERSONAL,
    CASHFLOW_EXPECTED_INCOME_FILE,
    CASHFLOW_GOAL_FILE,
    CASHFLOW_INVESTABLE_INCOME_CATEGORIES,
    CASHFLOW_RESERVE_BALANCE_FILE,
    CASHFLOW_RESERVE_TARGET_FILE,
    CASHFLOW_TRANSACTIONS_FILE,
    EXPENSE_CATEGORY_TYPE,
    NOTGROSCHEN_TARGET,
    SAVINGS_RATE_MIN_INCOME,
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
    question: Optional[str] = None     # why it's flagged, e.g. "which category: Groceries or Dining?"
    question_type: Literal["category", "freetext"] = "freetext"


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
    """Income totals per category for ``month``.

    Categories in ``CASHFLOW_EXCLUDE_FROM_PERSONAL`` (e.g. a roommate's rent
    pass-through reimbursement) are left out — same mechanism and same reason
    as :func:`monthly_expenses_by_category`: it's real money moving through
    the account, not personal income, so every "what did I actually earn"
    view should skip it while the raw Transactions list still shows it.
    """
    totals: dict[str, float] = defaultdict(float)
    for e in entries_for_month(month):
        if e.direction == "income" and e.category not in CASHFLOW_EXCLUDE_FROM_PERSONAL:
            totals[e.category] += e.amount
    return {k: round(v, 2) for k, v in totals.items()}


def monthly_expenses_by_category(month: str) -> list[dict]:
    """Expense totals per category for ``month``, sorted descending.

    Categories in ``CASHFLOW_EXCLUDE_FROM_PERSONAL`` (e.g. work-reimbursed
    meals) are left out — this feeds every "what did I actually spend" view
    (summary totals, trend, spending tab, spike alerts), not the raw
    Transactions list, which still shows those rows individually.
    """
    totals: dict[str, float] = defaultdict(float)
    for e in entries_for_month(month):
        if e.direction == "expense" and e.category not in CASHFLOW_EXCLUDE_FROM_PERSONAL:
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


def get_reserve_target() -> float:
    """Notgroschen reserve target — ``NOTGROSCHEN_TARGET`` unless overridden via
    :func:`set_reserve_target` (Cash Flow Overview tab's "Set target" editor)."""
    return _load_json(CASHFLOW_RESERVE_TARGET_FILE).get("target", NOTGROSCHEN_TARGET)


def set_reserve_target(value: float) -> None:
    _save_json(CASHFLOW_RESERVE_TARGET_FILE, {"target": value})
    logger.info("Reserve target set to %.2f", value)


def reserve_status(month: str) -> dict:
    """Latest recorded reserve balance on/before ``month``, vs. the Notgroschen target."""
    data = _load_json(CASHFLOW_RESERVE_BALANCE_FILE)
    target = get_reserve_target()
    months = sorted(m for m in data if m <= month)
    balance = data[months[-1]] if months else None
    percent_filled = round(min(100.0, balance / target * 100), 1) if balance is not None else None
    remaining = round(max(0.0, target - balance), 2) if balance is not None else None
    return {
        "month": month, "reserve_balance": balance, "target": target,
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


# --- Accounts (where cash sits) ----------------------------------------------
# Hand-maintained snapshot of current account balances, for the Overview
# accounts strip. Separate from the reserve-balance history above (that feeds
# the historical reserve/invest split for past months); this is "right now".

def list_accounts() -> list[dict]:
    return _load_json(CASHFLOW_ACCOUNTS_FILE).get("accounts", [])


def set_account(name: str, balance: float, is_reserve: bool = False) -> list[dict]:
    """Add or update one account by name. Setting ``is_reserve`` clears the
    flag on every other account first — only one account can be the
    Notgroschen reserve."""
    accounts = list_accounts()
    if is_reserve:
        for a in accounts:
            a["is_reserve"] = False
    for a in accounts:
        if a["name"] == name:
            a["balance"] = balance
            a["is_reserve"] = is_reserve
            break
    else:
        accounts.append({"name": name, "balance": balance, "is_reserve": is_reserve})
    _save_json(CASHFLOW_ACCOUNTS_FILE, {"accounts": accounts})
    logger.info("Account %s set to %.2f (reserve=%s)", name, balance, is_reserve)
    return accounts


def delete_account(name: str) -> list[dict]:
    accounts = [a for a in list_accounts() if a["name"] != name]
    _save_json(CASHFLOW_ACCOUNTS_FILE, {"accounts": accounts})
    return accounts


def accounts_summary() -> dict:
    """Every tracked account plus total cash, for the Overview accounts strip."""
    accounts = list_accounts()
    return {"accounts": accounts, "total_cash": round(sum(a["balance"] for a in accounts), 2)}


# --- Investable surplus + reserve/invest split (Mehrkontenmodell) -----------

def investable_income(month: str) -> float:
    """Sum of income whose category counts as real earned surplus."""
    by_cat = monthly_income_by_category(month)
    return round(sum(v for c, v in by_cat.items() if c in CASHFLOW_INVESTABLE_INCOME_CATEGORIES), 2)


def investable_surplus(month: str) -> float:
    expenses_total = sum(c["amount"] for c in monthly_expenses_by_category(month))
    return round(investable_income(month) - expenses_total, 2)


def _split_waterfall(surplus: float, balance: float, target: float) -> tuple[float, float]:
    """(to_reserve, to_invest) for one month's ``surplus``: fill the reserve to
    ``target`` first (capped at ``SPLIT_RATIO_TO_RESERVE`` of surplus), then
    route the rest to investments. Negative/zero surplus routes nothing
    anywhere rather than recommending a "negative" allocation.
    """
    if surplus <= 0:
        return 0.0, 0.0
    if balance < target:
        to_reserve = round(min(surplus * SPLIT_RATIO_TO_RESERVE, target - balance), 2)
        return to_reserve, round(surplus - to_reserve, 2)
    return 0.0, round(surplus, 2)


def split_recommendation(month: str) -> dict:
    """This month's actual waterfall split, from real ledger income/expenses."""
    surplus = investable_surplus(month)
    reserve = reserve_status(month)
    balance = reserve["reserve_balance"] or 0.0
    target = reserve["target"]
    to_reserve, to_invest = _split_waterfall(surplus, balance, target)

    income_total = investable_income(month)
    savings_rate = round(surplus / income_total, 4) if income_total else None

    return {
        "month": month, "surplus": surplus, "to_reserve": to_reserve, "to_invest": to_invest,
        "reserve": reserve, "savings_rate": savings_rate,
    }


# --- Overview tab aggregation --------------------------------------------

def _prior_months(month: str, n: int) -> list[str]:
    """The ``n`` most recent available months strictly before ``month``, or
    ``[]`` if fewer than ``n`` exist (trailing averages need a full window)."""
    prior = [m for m in available_months() if m < month]
    return prior[-n:] if len(prior) >= n else []


def _trailing_avg_and_delta(month: str, this_value: float, field: str, window: int = 3) -> tuple[Optional[float], Optional[float]]:
    """``field``'s average over the ``window`` months before ``month`` and this
    month's % delta vs. that average. ``(None, None)`` with less than a full
    window of history; delta is ``None`` (not divide-by-zero) when the average
    itself is 0."""
    prior = _prior_months(month, window)
    if not prior:
        return None, None
    avg = round(sum(monthly_summary(m)[field] for m in prior) / len(prior), 2)
    delta = round((this_value - avg) / abs(avg) * 100, 1) if avg else None
    return avg, delta


def guarded_savings_rate(income_total: float, net: float) -> Optional[float]:
    """Net / income, or ``None`` when income is too close to zero for the
    ratio to mean anything (see ``SAVINGS_RATE_MIN_INCOME``)."""
    if income_total < SAVINGS_RATE_MIN_INCOME:
        return None
    return round(net / income_total, 4)


def top_categories(month: str, n: int = 3) -> list[dict]:
    """The ``n`` largest expense categories for ``month``, each with its share
    of total expenses."""
    cats = monthly_expenses_by_category(month)
    total = sum(c["amount"] for c in cats)
    return [
        {
            "category": c["category"],
            "amount": c["amount"],
            "percent_of_total": round(c["amount"] / total * 100, 1) if total else 0.0,
        }
        for c in cats[:n]
    ]


def biggest_movers(month: str) -> list[dict]:
    """Every expense category with a trailing 3-month average to compare
    against, sorted by % change vs. that average (largest increase first).
    ``[]`` without a full 3-month window. Categories with a zero/negative
    prior average are excluded — there's nothing meaningful to compare to."""
    prior = _prior_months(month, 3)
    if not prior:
        return []
    this_month = {c["category"]: c["amount"] for c in monthly_expenses_by_category(month)}
    prior_totals: dict[str, float] = defaultdict(float)
    for m in prior:
        for c in monthly_expenses_by_category(m):
            prior_totals[c["category"]] += c["amount"]

    rows = []
    for category, amount in this_month.items():
        avg = prior_totals.get(category, 0.0) / len(prior)
        if avg <= 0:
            continue
        delta_percent = round((amount - avg) / avg * 100, 1)
        rows.append({"category": category, "amount": amount, "avg_3mo": round(avg, 2), "delta_percent": delta_percent})
    rows.sort(key=lambda r: r["delta_percent"], reverse=True)
    return rows


def biggest_mover(month: str) -> Optional[dict]:
    """The single category with the largest % increase vs. its trailing
    3-month average, as ``{category, delta_percent}`` — ``None`` if nothing
    both has spending this month and rose vs. a positive prior average."""
    movers = biggest_movers(month)
    if not movers or movers[0]["delta_percent"] <= 0:
        return None
    return {"category": movers[0]["category"], "delta_percent": movers[0]["delta_percent"]}


def overview(month: str) -> dict:
    """Everything the Cash Flow Overview tab needs for ``month`` in one call:
    KPI totals with trailing 3-month deltas, guarded savings rate, runway,
    reserve status + recommended split, top spending categories, and the
    biggest category mover.
    """
    summary = monthly_summary(month)
    income_avg, income_delta = _trailing_avg_and_delta(month, summary["income_total"], "income_total")
    expenses_avg, expenses_delta = _trailing_avg_and_delta(month, summary["expenses_total"], "expenses_total")
    net_avg, net_delta = _trailing_avg_and_delta(month, summary["net"], "net")
    split = split_recommendation(month)

    return {
        "month": month,
        "income": {"total": summary["income_total"], "avg_3mo": income_avg, "delta_percent": income_delta},
        "expenses": {"total": summary["expenses_total"], "avg_3mo": expenses_avg, "delta_percent": expenses_delta},
        "net": {"total": summary["net"], "avg_3mo": net_avg, "delta_percent": net_delta},
        # Guarded against investable income (not summary["income_total"]): a
        # no-salary month can still show a few hundred € of reimbursements/
        # gifts, which would clear the near-zero guard and yield a nonsense
        # ratio instead of "n/a".
        "savings_rate": guarded_savings_rate(investable_income(month), split["surplus"]),
        "runway_months": runway()["months_total"],
        "reserve": split["reserve"],
        "split_recommendation": {"to_reserve": split["to_reserve"], "to_invest": split["to_invest"]},
        "investable_surplus": split["surplus"],
        "top_categories": top_categories(month),
        "biggest_mover": biggest_mover(month),
    }


# --- Spending tab (fixed/variable + recurring + drill-down) ------------------

def expense_category_type(category: str) -> str:
    """"fixed" or "variable" for one category (``EXPENSE_CATEGORY_TYPE`` in
    core/config.py; unlisted categories default to "variable")."""
    return EXPENSE_CATEGORY_TYPE.get(category, "variable")


def monthly_fixed_vs_variable(month: str) -> dict:
    """Fixed vs. variable expense totals for ``month``, plus the fixed share
    of total spend."""
    by_cat = monthly_expenses_by_category(month)
    fixed = round(sum(c["amount"] for c in by_cat if expense_category_type(c["category"]) == "fixed"), 2)
    variable = round(sum(c["amount"] for c in by_cat if expense_category_type(c["category"]) != "fixed"), 2)
    total = fixed + variable
    return {
        "month": month,
        "fixed": fixed,
        "variable": variable,
        "fixed_share": round(fixed / total, 4) if total else None,
    }


def category_detail(month: str, category: str) -> list[dict]:
    """Merchants within ``category`` for ``month``, with totals, descending."""
    totals: dict[str, float] = defaultdict(float)
    for e in entries_for_month(month):
        if e.direction == "expense" and e.category == category:
            totals[e.description.strip()] += e.amount
    rows = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return [{"merchant": k, "amount": round(v, 2)} for k, v in rows]


# Interval bands (days between consecutive charges) a merchant's cadence must
# fall entirely within to count as "recurring" rather than just frequent.
_RECURRING_CADENCE_BANDS: list[tuple[str, int, int]] = [
    ("weekly", 6, 8),
    ("monthly", 25, 35),
    ("quarterly", 85, 95),
    ("yearly", 350, 380),
]
# Monthly-equivalent multiplier for each cadence's average per-charge amount.
_CADENCE_MONTHLY_FACTOR: dict[str, float] = {
    "weekly": 4.33,
    "monthly": 1.0,
    "quarterly": 1 / 3,
    "yearly": 1 / 12,
}
# Max (max - min) / avg amount spread across occurrences to still count as
# "roughly constant" — wider than this and it's not a fixed-price subscription.
_RECURRING_AMOUNT_SPREAD_MAX = 0.20
# Minimum rise (last vs. prior occurrence) flagged as price creep.
_PRICE_CREEP_THRESHOLD = 0.03
# Weekly cadence needs more than one interval to rule out a coincidental
# 6-8 day gap between two otherwise-unrelated visits (e.g. two vacation-week
# meals); monthly/quarterly/yearly are distinctive enough at 2 occurrences.
_MIN_OCCURRENCES_BY_CADENCE: dict[str, int] = {"weekly": 3}


def _classify_cadence(intervals: list[int]) -> Optional[str]:
    for name, lo, hi in _RECURRING_CADENCE_BANDS:
        if all(lo <= d <= hi for d in intervals):
            return name
    return None


def recurring_charges(months: int = 6) -> dict:
    """Merchants billing on a regular cadence with a roughly constant amount,
    detected over the trailing ``months`` of ledger history — i.e. recurring
    charges / subscriptions, not just frequently-visited merchants (a corner
    shop visited weekly at varying amounts doesn't qualify; Netflix does).

    Returns ``{"items": [...], "committed_monthly_total": ...}`` — each item
    is ``{merchant, amount, cadence, category, last_seen, occurrences,
    price_creep, price_creep_delta}``, sorted by monthly-equivalent spend
    descending. ``price_creep`` flags a >=3% rise on the most recent charge
    vs. the one before it.
    """
    window = available_months()[-months:] if months else available_months()
    entries = [e for e in list_entries() if e.direction == "expense" and e.date.strftime("%Y-%m") in window]

    by_merchant: dict[str, list[CashflowEntry]] = defaultdict(list)
    for e in entries:
        by_merchant[e.description.strip().lower()].append(e)

    items = []
    committed_monthly_total = 0.0
    for rows in by_merchant.values():
        if len(rows) < 2:
            continue
        rows = sorted(rows, key=lambda e: e.date)
        intervals = [(rows[i].date - rows[i - 1].date).days for i in range(1, len(rows))]
        cadence = _classify_cadence(intervals)
        if cadence is None or len(rows) < _MIN_OCCURRENCES_BY_CADENCE.get(cadence, 2):
            continue
        amounts = [r.amount for r in rows]
        avg_amount = sum(amounts) / len(amounts)
        if avg_amount <= 0 or (max(amounts) - min(amounts)) / avg_amount > _RECURRING_AMOUNT_SPREAD_MAX:
            continue

        last, prev = rows[-1], rows[-2]
        price_creep = last.amount > prev.amount * (1 + _PRICE_CREEP_THRESHOLD)
        monthly_equivalent = avg_amount * _CADENCE_MONTHLY_FACTOR[cadence]
        committed_monthly_total += monthly_equivalent
        items.append({
            "merchant": last.description.strip(),
            "amount": round(avg_amount, 2),
            "cadence": cadence,
            "category": last.category,
            "last_seen": last.date.isoformat(),
            "occurrences": len(rows),
            "price_creep": price_creep,
            "price_creep_delta": round(last.amount - prev.amount, 2) if price_creep else None,
            "monthly_equivalent": round(monthly_equivalent, 2),
        })

    items.sort(key=lambda i: i["monthly_equivalent"], reverse=True)
    return {"items": items, "committed_monthly_total": round(committed_monthly_total, 2)}


def spending(month: str) -> dict:
    """Everything the Cash Flow Spending tab needs for ``month`` in one call:
    fixed-vs-variable split, recurring/subscription detection with a
    committed-monthly total, per-category totals with merchant drill-down,
    and the full biggest-movers list vs. each category's 3-month average."""
    by_cat = monthly_expenses_by_category(month)
    categories = [
        {
            "category": c["category"],
            "amount": c["amount"],
            "type": expense_category_type(c["category"]),
            "merchants": category_detail(month, c["category"]),
        }
        for c in by_cat
    ]
    return {
        "month": month,
        "fixed_vs_variable": monthly_fixed_vs_variable(month),
        "recurring": recurring_charges(),
        "categories": categories,
        "biggest_movers": biggest_movers(month),
    }


# --- Forecast tab (runway, forward projection, scenarios, trends) -----------
# Average days per calendar month (365.25 / 12) — used only to turn a
# fractional month count into an approximate calendar date for display
# ("cash lasts until ~12 Dec 2026"); never used for the whole-month stepping
# in forward_forecast(), which walks real calendar months instead.
_AVG_DAYS_PER_MONTH = 30.44


def get_expected_monthly_income() -> Optional[float]:
    """Manual override for forward_forecast()'s recurring-income assumption —
    e.g. David's known upcoming salary before any "Salary" category rows
    exist in the ledger yet. ``None`` when unset (forecast falls back to the
    trailing Salary-category average)."""
    return _load_json(CASHFLOW_EXPECTED_INCOME_FILE).get("monthly_amount")


def set_expected_monthly_income(value: Optional[float]) -> None:
    data = _load_json(CASHFLOW_EXPECTED_INCOME_FILE)
    if value is None:
        data.pop("monthly_amount", None)
    else:
        data["monthly_amount"] = value
    _save_json(CASHFLOW_EXPECTED_INCOME_FILE, data)
    logger.info("Expected monthly income set to %s", value)


def _shift_month(month: str, n: int) -> str:
    """``month`` (``"YYYY-MM"``) shifted forward ``n`` whole calendar months."""
    year, mon = (int(x) for x in month.split("-"))
    total = year * 12 + (mon - 1) + n
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def runway(as_of: Optional[date] = None) -> dict:
    """Total cash / average monthly burn (fixed + variable), as both a month
    count and an approximate "cash lasts until" date. Also reports the point
    at which spending would start drawing down the €4.000 reserve itself —
    i.e. runway on non-reserve cash alone — since the reserve balance isn't a
    fair stand-in for the total horizon and would understate it.
    """
    as_of = as_of or date.today()
    accounts = accounts_summary()
    has_accounts = bool(accounts["accounts"])
    total_cash = accounts["total_cash"]
    reserve_balance = next((a["balance"] for a in accounts["accounts"] if a.get("is_reserve")), 0.0)
    non_reserve_cash = max(0.0, total_cash - reserve_balance)

    window = available_months()[-3:] or available_months()
    monthly_burn = round(sum(monthly_summary(m)["expenses_total"] for m in window) / len(window), 2) if window else None

    def _months_and_date(cash: float) -> tuple[Optional[float], Optional[str]]:
        if not monthly_burn or not has_accounts:
            return None, None
        months = round(cash / monthly_burn, 1)
        lasts_until = (as_of + timedelta(days=months * _AVG_DAYS_PER_MONTH)).isoformat()
        return months, lasts_until

    months_total, cash_lasts_until = _months_and_date(total_cash)
    months_before_reserve, reserve_drawdown_date = _months_and_date(non_reserve_cash)

    return {
        "as_of": as_of.isoformat(),
        "total_cash": total_cash,
        "reserve_balance": reserve_balance,
        "monthly_burn": monthly_burn,
        "months_total": months_total,
        "cash_lasts_until": cash_lasts_until,
        "months_before_reserve_drawdown": months_before_reserve,
        "reserve_drawdown_date": reserve_drawdown_date,
    }


def runway_scenarios() -> dict:
    """Runway recomputed under two simple levers: cutting trailing-average
    variable spend by 25% or 50%. ``None`` scenarios when there's no ledger
    history yet to derive a variable-spend baseline from, or no accounts yet
    to project runway from (matching :func:`runway`'s own guard — otherwise
    a cut-spend scenario would show a misleading "0 months, lasts until
    today" instead of "no data yet")."""
    base = runway()
    window = available_months()[-3:] or available_months()
    if not window or not base["monthly_burn"] or base["months_total"] is None:
        return {"base": base, "cut_variable_25": None, "cut_variable_50": None}

    total_cash = base["total_cash"]
    as_of = date.fromisoformat(base["as_of"])
    variable_avg = round(sum(monthly_fixed_vs_variable(m)["variable"] for m in window) / len(window), 2)

    scenarios: dict[str, Optional[dict]] = {}
    for pct, key in ((0.25, "cut_variable_25"), (0.5, "cut_variable_50")):
        new_burn = round(base["monthly_burn"] - variable_avg * pct, 2)
        if new_burn <= 0:
            scenarios[key] = {"monthly_burn": new_burn, "months_total": None, "cash_lasts_until": None}
            continue
        months_total = round(total_cash / new_burn, 1)
        lasts_until = (as_of + timedelta(days=months_total * _AVG_DAYS_PER_MONTH)).isoformat()
        scenarios[key] = {"monthly_burn": new_burn, "months_total": months_total, "cash_lasts_until": lasts_until}

    return {"base": base, **scenarios}


def forward_forecast(months: int = 6) -> dict:
    """Project the next ``months`` calendar months forward from recurring
    income (Salary once it's in the ledger, or David's manual
    :func:`get_expected_monthly_income` override) minus recurring/committed
    bills (trailing average of fixed-category expenses). Each projected month
    applies the same 70/30 reserve waterfall as :func:`split_recommendation`,
    carrying the projected reserve balance forward — surfacing the reserve-
    fill date (€4.000) and the month 70/30 investing begins.
    """
    avail = available_months()
    base_month = avail[-1] if avail else date.today().strftime("%Y-%m")
    window = avail[-3:] or avail

    recurring_income = get_expected_monthly_income()
    if recurring_income is None:
        salary_months = [v for m in window if (v := monthly_income_by_category(m).get("Salary", 0.0)) > 0]
        recurring_income = round(sum(salary_months) / len(salary_months), 2) if salary_months else 0.0

    committed_bills = round(sum(monthly_fixed_vs_variable(m)["fixed"] for m in window) / len(window), 2) if window else 0.0

    target = get_reserve_target()
    reserve_balance = reserve_status(base_month)["reserve_balance"] or 0.0

    rows: list[dict] = []
    reserve_fill_month: Optional[str] = None
    invest_start_month: Optional[str] = None
    for i in range(1, months + 1):
        m = _shift_month(base_month, i)
        surplus = round(recurring_income - committed_bills, 2)
        to_reserve, to_invest = _split_waterfall(surplus, reserve_balance, target)
        reserve_balance = round(reserve_balance + to_reserve, 2)
        if reserve_fill_month is None and reserve_balance >= target:
            reserve_fill_month = m
        if invest_start_month is None and to_invest > 0:
            invest_start_month = m
        rows.append({
            "month": m,
            "projected_income": recurring_income,
            "projected_bills": committed_bills,
            "projected_surplus": surplus,
            "to_reserve": to_reserve,
            "to_invest": to_invest,
            "projected_reserve_balance": reserve_balance,
        })

    return {
        "base_month": base_month,
        "recurring_income": recurring_income,
        "committed_bills": committed_bills,
        "reserve_target": target,
        "months": rows,
        "reserve_fill_month": reserve_fill_month,
        "invest_start_month": invest_start_month,
    }


def trends(months: int = 12) -> list[dict]:
    """Monthly ``{month, savings_rate, income_stability}`` series: guarded
    savings rate, and income stability (the "Salary" category's share of
    total income — recurring pay vs. one-off freelance/gifts/reimbursements).
    ``income_stability`` is ``None`` for months with no income at all."""
    window = available_months()[-months:] if months else available_months()
    out = []
    for m in window:
        summary = monthly_summary(m)
        salary = monthly_income_by_category(m).get("Salary", 0.0)
        income_stability = round(salary / summary["income_total"], 4) if summary["income_total"] else None
        out.append({
            "month": m,
            "savings_rate": guarded_savings_rate(investable_income(m), investable_surplus(m)),
            "income_stability": income_stability,
        })
    return out


# --- Alerts engine (Phase 10) -------------------------------------------
# Feeds both the Overview alerts strip and the weekly briefing. Two kinds:
# category/recurring alerts (evaluated purely from `month`'s own data) and
# point-in-time alerts — runway, reserve milestones — which describe "now"
# rather than a historical month, so they only fire when `month` is the most
# recent one with ledger data (never for a month David is just reviewing).
_ALERT_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _category_spike_alerts(month: str) -> list[dict]:
    """A category running >= ``CASHFLOW_ALERT_CATEGORY_SPIKE_MULTIPLIER`` its
    trailing 3-month average (e.g. 2x -> a >=100% delta)."""
    threshold_percent = (CASHFLOW_ALERT_CATEGORY_SPIKE_MULTIPLIER - 1) * 100
    alerts = []
    for m in biggest_movers(month):
        if m["delta_percent"] < threshold_percent:
            continue
        alerts.append({
            "type": "category_spike",
            "severity": "high" if m["delta_percent"] >= 2 * threshold_percent else "medium",
            "message": (
                f"{m['category']} spending is {m['amount']:.0f}€ this month — "
                f"{m['delta_percent']:.0f}% above its 3-month average of {m['avg_3mo']:.0f}€"
            ),
            "tab": "spending",
        })
    return alerts


def _recurring_alerts(month: str) -> list[dict]:
    """A recurring/subscription charge newly detected this month (just crossed
    the occurrence threshold for its cadence), or an existing one whose price
    just rose."""
    alerts = []
    for item in recurring_charges()["items"]:
        if item["last_seen"][:7] != month:
            continue
        if item["occurrences"] == _MIN_OCCURRENCES_BY_CADENCE.get(item["cadence"], 2):
            alerts.append({
                "type": "new_recurring",
                "severity": "medium",
                "message": (
                    f"newly detected recurring charge: {item['merchant']} — "
                    f"{item['amount']:.2f}€ {item['cadence']}"
                ),
                "tab": "spending",
            })
        if item["price_creep"]:
            alerts.append({
                "type": "price_creep",
                "severity": "medium",
                "message": (
                    f"{item['merchant']} price rose {item['price_creep_delta']:.2f}€ "
                    f"— now {item['amount']:.2f}€ {item['cadence']}"
                ),
                "tab": "spending",
            })
    return alerts


def _runway_alert(month: str) -> list[dict]:
    r = runway()
    if r["months_total"] is None or r["months_total"] >= CASHFLOW_ALERT_RUNWAY_MONTHS:
        return []
    return [{
        "type": "low_runway",
        "severity": "high" if r["months_total"] < 1 else "medium",
        "message": (
            f"runway is {r['months_total']:.1f} months at current burn — "
            f"cash lasts until {r['cash_lasts_until']}"
        ),
        "tab": "overview",
    }]


def _reserve_milestone_alerts(month: str) -> list[dict]:
    current = reserve_status(month)
    if current["reserve_balance"] is None:
        return []
    # Prior month by reserve-balance history (not the ledger's available_months)
    # — reserve snapshots and cashflow entries are recorded independently.
    balance_months = sorted(m for m in _load_json(CASHFLOW_RESERVE_BALANCE_FILE) if m < month)
    prior_percent_filled = reserve_status(balance_months[-1])["percent_filled"] if balance_months else None

    if current["percent_filled"] is not None and current["percent_filled"] >= 100 and (
        prior_percent_filled is None or prior_percent_filled < 100
    ):
        return [{
            "type": "reserve_full",
            "severity": "low",
            "message": "safety reserve is full — investing begins",
            "tab": "reserve",
        }]
    remaining = current["remaining_to_target"]
    if remaining is not None and 0 < remaining <= CASHFLOW_ALERT_RESERVE_NEAR_FULL:
        return [{
            "type": "reserve_near_full",
            "severity": "low",
            "message": f"€{remaining:.0f} to go until the safety reserve is full",
            "tab": "reserve",
        }]
    return []


def alerts(month: str) -> list[dict]:
    """Every active alert for ``month``: category spikes, new/rising recurring
    charges, and — only when ``month`` is the latest one with ledger data —
    low runway and reserve milestones. Sorted by severity (high first); each
    alert carries a stable ``id`` (content hash) so the frontend can dismiss
    it without a persisted "seen" store.
    """
    items = _category_spike_alerts(month) + _recurring_alerts(month)
    avail = available_months()
    if not avail or month == avail[-1]:
        items += _runway_alert(month) + _reserve_milestone_alerts(month)
    items.sort(key=lambda a: _ALERT_SEVERITY_RANK.get(a["severity"], 3))
    for a in items:
        raw = f"{month}|{a['type']}|{a['message']}"
        a["id"] = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return items
