"""Positions + transactions data layer (Phase 15a finance foundation).

A more sophisticated holdings model than the legacy ``portfolio.py`` (which read
point-in-time snapshots straight from ``Finance_Tracker.xlsx``). Here, current
holdings are *derived* from an append-only transaction log, so cost basis,
realized P&L and time-varying weights all become computable.

Storage (both in the repo's ``data/`` dir, gitignored — never the vault):
- ``positions.json``  — per-ticker static metadata (name, type, bucket, sector…)
- ``transactions.jsonl`` — one JSON transaction per line, append-only

The legacy ``portfolio.py`` stays in place; new code uses this module.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel

from core.config import POSITIONS_FILE, TRANSACTIONS_FILE, get_logger

logger = get_logger(__name__)

PositionType = Literal["equity", "etf", "crypto", "cash"]
Bucket = Literal["etf_foundation", "single_stocks", "crypto", "wild_cards"]
Action = Literal["buy", "sell", "dividend", "split", "deposit", "withdraw"]

# Actions that change the share/coin count of a holding (and so feed holdings +
# cost basis). ``dividend`` / ``deposit`` / ``withdraw`` are cash events that do
# not move the position quantity.
_QUANTITY_ACTIONS = {"buy", "sell"}


class Position(BaseModel):
    """Static metadata for a tradeable instrument (not the quantity held)."""

    ticker: str
    name: str
    type: PositionType
    bucket: Bucket
    sector: Optional[str] = None
    region: Optional[str] = None
    currency: str = "USD"


class Transaction(BaseModel):
    """A single dated event against a ticker. Quantities/prices in ``currency``."""

    date: date
    ticker: str
    action: Action
    quantity: float
    price: float
    currency: str = "USD"
    fees: float = 0.0
    notes: Optional[str] = None


# --- Positions (positions.json) ---------------------------------------------

def list_positions() -> list[Position]:
    """All known positions (empty list if the store doesn't exist yet)."""
    if not POSITIONS_FILE.exists():
        return []
    try:
        raw = json.loads(POSITIONS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:  # noqa: BLE001
        logger.warning("positions.json unreadable: %s", exc)
        return []
    return [Position(**row) for row in raw]


def get_position(ticker: str) -> Optional[Position]:
    """Look up one position's metadata by ticker (case-insensitive)."""
    tu = ticker.upper()
    for p in list_positions():
        if p.ticker.upper() == tu:
            return p
    return None


def add_position(p: Position) -> None:
    """Insert or replace a position's metadata (keyed by ticker)."""
    POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = {pos.ticker.upper(): pos for pos in list_positions()}
    existing[p.ticker.upper()] = p
    ordered = sorted(existing.values(), key=lambda x: x.ticker)
    POSITIONS_FILE.write_text(
        json.dumps([pos.model_dump() for pos in ordered], indent=2),
        encoding="utf-8",
    )
    logger.info("Saved position %s", p.ticker)


# --- Transactions (transactions.jsonl) --------------------------------------

def list_transactions() -> list[Transaction]:
    """Every recorded transaction, in file (chronological-append) order."""
    if not TRANSACTIONS_FILE.exists():
        return []
    out: list[Transaction] = []
    for line in TRANSACTIONS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(Transaction(**json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:  # noqa: BLE001
            logger.warning("Skipping malformed transaction line: %s", exc)
    return out


def record_transaction(t: Transaction) -> None:
    """Append one transaction to the JSONL log (creates the file if needed)."""
    TRANSACTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = t.model_dump()
    payload["date"] = t.date.isoformat()  # date -> ISO string for JSON
    with TRANSACTIONS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")
    logger.info("Recorded %s %s %s @ %s", t.action, t.quantity, t.ticker, t.price)


def transactions_for(ticker: str) -> list[Transaction]:
    """All transactions for one ticker, sorted by date (case-insensitive)."""
    tu = ticker.upper()
    rows = [t for t in list_transactions() if t.ticker.upper() == tu]
    return sorted(rows, key=lambda t: t.date)


# --- Derived views ----------------------------------------------------------

def current_holdings() -> dict[str, float]:
    """Net quantity per ticker from all buys (+) and sells (−).

    Positions that net to ~zero are dropped. Keys are the canonical tickers as
    recorded on the transactions.
    """
    totals: dict[str, float] = {}
    for t in list_transactions():
        if t.action not in _QUANTITY_ACTIONS:
            continue
        sign = 1.0 if t.action == "buy" else -1.0
        totals[t.ticker] = totals.get(t.ticker, 0.0) + sign * t.quantity
    return {tk: round(q, 8) for tk, q in totals.items() if abs(q) > 1e-9}


def cost_basis(ticker: str, as_of: Optional[date] = None) -> tuple[float, float]:
    """FIFO cost basis for the held shares of ``ticker`` (today, or ``as_of``).

    Returns ``(avg_cost, total_basis)``. Sells consume the oldest buy lots first
    (FIFO); the remaining open lots define the basis. Fees are folded into each
    buy lot's cost. With nothing held, returns ``(0.0, 0.0)``. When ``as_of`` is
    given, only transactions on/before that date are replayed — used by the
    backfill to value historical positions at their then-current basis.
    """
    lots: list[list[float]] = []  # each: [remaining_qty, per_share_cost]
    for t in transactions_for(ticker):
        if as_of is not None and t.date > as_of:
            break
        if t.action == "buy":
            per_share = t.price + (t.fees / t.quantity if t.quantity else 0.0)
            lots.append([t.quantity, per_share])
        elif t.action == "sell":
            to_remove = t.quantity
            while to_remove > 1e-9 and lots:
                lot = lots[0]
                take = min(lot[0], to_remove)
                lot[0] -= take
                to_remove -= take
                if lot[0] <= 1e-9:
                    lots.pop(0)
    total_qty = sum(lot[0] for lot in lots)
    total_basis = sum(lot[0] * lot[1] for lot in lots)
    avg_cost = total_basis / total_qty if total_qty > 1e-9 else 0.0
    return round(avg_cost, 6), round(total_basis, 2)


def holdings_asof(as_of: date) -> dict[str, float]:
    """Net quantity per ticker from buys/sells on or before ``as_of``.

    Same netting as :func:`current_holdings` but truncated to a date, so the
    backfill can reconstruct how many shares were held on each historical day.
    """
    totals: dict[str, float] = {}
    for t in list_transactions():
        if t.action not in _QUANTITY_ACTIONS or t.date > as_of:
            continue
        sign = 1.0 if t.action == "buy" else -1.0
        totals[t.ticker] = totals.get(t.ticker, 0.0) + sign * t.quantity
    return {tk: round(q, 8) for tk, q in totals.items() if abs(q) > 1e-9}


def first_transaction_date(ticker: str) -> Optional[date]:
    """Date of the earliest transaction for ``ticker`` (None if none)."""
    txns = transactions_for(ticker)
    return txns[0].date if txns else None
