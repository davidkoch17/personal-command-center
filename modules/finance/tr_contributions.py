"""Monthly Trade Republic contribution tracking.

"Contribution" here means net *new* money moved into the TR depot in a given
month — deposits minus withdrawals — as distinct from market gains/losses on
whatever's already held. This feeds the surplus-split sanity check in
``backend/api/money.py``'s ``/allocation/{month}``: comparing what was actually
moved into the depot against ``split_recommendation()``'s ``to_invest``.

Three sources, in order of trust:

1. **Explicit deposit/withdraw ledger entries** — the real number, once the TR
   statement parser (``tr_statement_parser.py``) records them. It currently
   only reconciles the statement's *holdings* table (equity quantities), not a
   cash-movements section, since no sample statement was available to see what
   that section looks like — so this path is wired but will find nothing until
   that parser is extended. Booked against the ``CASH_TICKER`` pseudo-ticker
   (see ``positions.py``) since a deposit isn't tied to one instrument.
2. **Manual override** (``set_override`` / ``get_override``) — David's
   hand-entered figure for a month the estimate can't be trusted for.
3. **Estimate**: ``(depot value change month-over-month) - (market P&L on
   positions held)``, reusing the exact per-ticker ``value_asof`` /
   ``net_contributions_between`` helpers ``period_pnl.py`` already built for
   the Overview tab's savings-vs-market-P&L decomposition. Depot value comes
   from the Investments_TR sheet's monthly totals (the only place TR cash is
   currently recorded at all); market P&L is scoped to
   ``positions.BROKERAGE_TYPES`` tickers so a Kraken/crypto move never gets
   misread as a TR contribution.

The estimate refuses to guess (returns ``None`` + a flag) when the workbook
has no snapshot for the month or the prior month, or when either snapshot's
Notes are marked as an estimate in the workbook itself (e.g. the April 2026
rows' "April-end estimate" note) — chaining an estimate on top of an estimate
compounds error silently, which is exactly what this module exists to avoid.

**Dependency**: this whole module is only as trustworthy as the TR statement
parser (Prompt 3) it's built on top of. Until that parser is verified against
a real statement, treat every non-override, non-explicit-deposit result here
as a best-effort estimate, not a fact.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date

from core.config import CONTRIBUTION_OVERRIDES_FILE, get_logger
from modules.finance.loader import investments_tr
from modules.finance.period_pnl import net_contributions_between, positions_daily_rows, value_asof
from modules.finance.positions import (
    BROKERAGE_TYPES,
    current_holdings,
    get_position,
    list_transactions,
    transactions_for,
)

logger = get_logger(__name__)


# --- month arithmetic ---------------------------------------------------------
def _month_bounds(month: str) -> tuple[date, date]:
    """(first day of ``month``, first day of the following month)."""
    year, mon = (int(x) for x in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1)
    return start, end


def _prev_month(month: str) -> str:
    year, mon = (int(x) for x in month.split("-"))
    return f"{year - 1:04d}-12" if mon == 1 else f"{year:04d}-{mon - 1:02d}"


# --- manual override store -----------------------------------------------------
def _load_overrides() -> dict[str, float]:
    if not CONTRIBUTION_OVERRIDES_FILE.exists():
        return {}
    try:
        return json.loads(CONTRIBUTION_OVERRIDES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:  # noqa: BLE001
        logger.warning("contribution_overrides.json unreadable: %s", exc)
        return {}


def get_override(month: str) -> float | None:
    return _load_overrides().get(month)


def set_override(month: str, value: float | None) -> None:
    """Set (or, with ``value=None``, clear) the manual override for ``month``."""
    overrides = _load_overrides()
    if value is None:
        overrides.pop(month, None)
    else:
        overrides[month] = value
    CONTRIBUTION_OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONTRIBUTION_OVERRIDES_FILE.write_text(json.dumps(overrides, indent=2), encoding="utf-8")
    logger.info("Contribution override for %s set to %s", month, value)


# --- explicit deposit/withdraw ledger entries ---------------------------------
def _explicit_deposits(month: str) -> float | None:
    """Sum of ``deposit``/``withdraw`` ledger transactions dated within ``month``.

    Returns ``None`` if there are none (not zero — "no data" and "confirmed
    zero net movement" are different things and callers need to tell them apart).
    """
    start, end = _month_bounds(month)
    total = 0.0
    found = False
    for t in list_transactions():
        if t.action not in ("deposit", "withdraw") or not (start <= t.date < end):
            continue
        found = True
        total += t.quantity if t.action == "deposit" else -t.quantity
    return round(total, 2) if found else None


# --- estimate: depot value change minus market P&L ----------------------------
def _tr_snapshot_month(month: str) -> "tuple[float | None, bool]":
    """(total Value (€) for ``month``'s Investments_TR rows, is-flagged-estimate).

    ``None`` total means no snapshot rows exist for that month at all.
    """
    df = investments_tr()
    if df.empty or "Month" not in df.columns or "Value (€)" not in df.columns:
        return None, False
    sub = df[df["Month"].astype(str) == month]
    if sub.empty:
        return None, False
    import pandas as pd

    total = float(pd.to_numeric(sub["Value (€)"], errors="coerce").sum())
    is_estimate = False
    if "Notes" in sub.columns:
        is_estimate = bool(sub["Notes"].astype(str).str.contains("estimate", case=False, na=False).any())
    return total, is_estimate


def _tr_market_pnl(month: str) -> tuple[float, list[str]]:
    """Price-driven P&L for the TR-scoped (equity/etf) depot during ``month``.

    Mirrors ``period_pnl.position_period_pnl``'s per-ticker formula
    (``value_end - value_start - net_contributions_in_window``), summed across
    every equity/etf ticker with any positions_daily.csv coverage touching the
    month — not just currently-held tickers, so a position fully closed mid-
    month still has its in-month price move counted.

    Also returns any ticker found "stale": no longer in ``current_holdings()``
    but with positions_daily.csv rows dated *after* its last ledger
    transaction. That means the daily snapshot job kept pricing a position
    after the ledger already closed it out — exactly what happened to GOOGL
    here (the daily job ran through 2026-07-19 pricing shares the 2026-07-13
    statement-reconciliation sell had already zeroed), because that job hasn't
    re-run since the ledger fix. Including such a ticker would silently price
    a position that, in reality, wasn't held for that stretch — callers should
    treat a non-empty stale list as "don't trust this month's market P&L".
    """
    start, end = _month_bounds(month)
    rows = positions_daily_rows()
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_ticker[r.get("ticker", "")].append(r)

    candidate_tickers = {
        ticker for ticker, snaps in by_ticker.items()
        if any(start.isoformat() <= s.get("date", "") < end.isoformat() for s in snaps)
        and (get_position(ticker).type if get_position(ticker) else "equity") in BROKERAGE_TYPES
    }

    held = current_holdings()
    stale: list[str] = []
    total_pnl = 0.0
    for ticker in candidate_tickers:
        v_end = value_asof(by_ticker, ticker, end, strictly_before=True) or 0.0
        v_start = value_asof(by_ticker, ticker, start, strictly_before=True) or 0.0
        contrib = net_contributions_between(ticker, start, end)
        total_pnl += v_end - v_start - contrib

        if ticker not in held:
            txns = transactions_for(ticker)
            last_txn_date = txns[-1].date.isoformat() if txns else None
            if last_txn_date and any(
                start.isoformat() <= s.get("date", "") < end.isoformat() and s.get("date", "") > last_txn_date
                for s in by_ticker.get(ticker, [])
            ):
                stale.append(ticker)

    return round(total_pnl, 2), stale


def _estimate(month: str) -> dict:
    """The value-change-minus-market-move estimate, with its own reliability flags."""
    prev = _prev_month(month)
    value_now, now_is_estimate = _tr_snapshot_month(month)
    value_prev, prev_is_estimate = _tr_snapshot_month(prev)
    market_pnl, stale_tickers = _tr_market_pnl(month)

    flags: list[str] = []
    if value_now is None:
        flags.append(f"no Investments_TR snapshot for {month}")
    if value_prev is None:
        flags.append(f"no Investments_TR snapshot for {prev} (needed as the prior-month baseline)")
    if now_is_estimate:
        flags.append(f"{month} Investments_TR snapshot is itself marked an estimate in its Notes")
    if prev_is_estimate:
        flags.append(f"{prev} Investments_TR snapshot is itself marked an estimate in its Notes")
    if stale_tickers:
        flags.append(
            f"positions_daily.csv has stale post-close pricing for {stale_tickers}: the "
            "daily snapshot job hasn't re-run since the ledger closed these positions out, "
            "so market P&L for this month isn't trustworthy yet"
        )

    if flags:
        return {"value": None, "reliable": False, "flags": flags,
                "depot_value_change": None, "market_pnl": None if stale_tickers else market_pnl}

    depot_value_change = round(value_now - value_prev, 2)
    value = round(depot_value_change - market_pnl, 2)
    return {
        "value": value, "reliable": True, "flags": [],
        "depot_value_change": depot_value_change, "market_pnl": market_pnl,
    }


# --- public entry point --------------------------------------------------------
def monthly_contribution(month: str) -> dict:
    """Net new money moved into the TR depot in ``month``.

    Precedence: explicit ledger deposit/withdraw entries > manual override >
    the value-change-minus-market-move estimate. The estimate is always
    computed and included under ``"estimate"`` for cross-checking, even when a
    higher-precedence source wins.

    Returns ``value: None`` (with ``flags`` explaining why) rather than a
    guessed number when the estimate can't be trusted and no override/explicit
    data exists — see module docstring.
    """
    estimate = _estimate(month)

    explicit = _explicit_deposits(month)
    if explicit is not None:
        return {
            "month": month, "value": explicit, "source": "explicit_deposits",
            "reliable": True, "flags": [], "estimate": estimate,
        }

    override = get_override(month)
    if override is not None:
        return {
            "month": month, "value": override, "source": "manual_override",
            "reliable": True, "flags": ["using David's manually entered override"],
            "estimate": estimate,
        }

    if estimate["reliable"]:
        return {
            "month": month, "value": estimate["value"], "source": "estimated",
            "reliable": True, "flags": [], "estimate": estimate,
        }

    return {
        "month": month, "value": None, "source": None, "reliable": False,
        "flags": estimate["flags"] + ["no manual override set — call set_override() or use the API to enter one"],
        "estimate": estimate,
    }
