"""Per-position period P&L + net-worth decomposition (Phase D Holdings/Overview).

The Holdings tab needs each position's P&L split three ways and the Overview tab
needs this month's net-worth change decomposed into savings vs market P&L. Both
are *derived* — never stored — from the daily history written by the Phase B
snapshot job plus the transaction ledger:

- ``positions_daily.csv``  (date, ticker, qty, price_eur, value_eur, cost_basis_eur)
- ``networth_daily.csv``   (date, bank_total, portfolio_total_eur, crypto_total_eur, debts_total, net_worth_eur)
- ``transactions.jsonl``   (the buy/sell ledger — for net contributions in a period)

P&L definitions (locked in the v3 spec § d):
- all-time = value - cost basis (unrealized).
- YTD      = (value - value at year-start) - net contributions YTD  (price-driven).
- month    = (value - value at month-start) - net contributions MTD (price-driven).

"Contributions-adjusted" isolates the price-driven gain: money moved into a
position mid-period would otherwise masquerade as a gain. Net contribution for a
ticker over a window = Σ buys(qty·price+fees) − Σ sells(qty·price−fees).

.. important:: **This module is a chart/analytics layer, not the source of
   truth for "net worth."** ``networth_daily.csv`` is built by re-pricing the
   ledger (``positions.json``/``transactions.jsonl``) against *live yfinance
   quotes* every day — a fast-moving, intraday-accurate but ledger-dependent
   number. The authoritative net worth is Excel (David hand-records it monthly
   in the ``Net_Worth`` sheet): ``modules.finance.money.latest_net_worth()``
   (served by ``GET /api/money/snapshot``) and its monthly trend in
   ``modules.finance.networth_history``. The two *will* disagree — a stale or
   incomplete ledger, an unrealized-vs-realized timing difference, or simply
   yfinance pricing something Excel hasn't been updated for yet — and that's
   expected, not a bug, precisely because they're built from different data.
   Never surface a number from this module (``networth_daily`` /
   ``month_decomposition``) as *the* net worth; use it only for the daily
   trend line and the savings-vs-market-P&L breakdown, both clearly scoped to
   "this is priced off the live ledger" in their own docstrings/UI captions.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Optional

from core.config import NETWORTH_DAILY_CSV, POSITIONS_DAILY_CSV, get_logger
from modules.finance._csv_store import read_rows
from modules.finance.positions import current_holdings, get_position, list_transactions

logger = get_logger(__name__)


# --- small parse helpers -----------------------------------------------------
def _f(value: object) -> float:
    """Best-effort float (blank/None/garbage -> 0.0)."""
    try:
        if value is None or value == "":
            return 0.0
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def month_start(on: date) -> date:
    return on.replace(day=1)


def year_start(on: date) -> date:
    return on.replace(month=1, day=1)


# --- positions_daily access --------------------------------------------------
def positions_daily_rows() -> list[dict]:
    """All positions_daily rows, sorted by date ascending.

    Public (not module-private) because :mod:`modules.finance.tr_contributions`
    reuses it, together with :func:`value_asof` / :func:`net_contributions_between`
    below, to compute a historical month's market P&L the same way this module
    does for "this month" — see that module's docstring for why.
    """
    rows = read_rows(POSITIONS_DAILY_CSV)
    return sorted(rows, key=lambda r: r.get("date", ""))


def value_asof(rows_by_ticker: dict[str, list[dict]], ticker: str,
               cutoff: date, *, strictly_before: bool) -> Optional[float]:
    """value_eur for ``ticker`` on the latest snapshot before/at ``cutoff``.

    ``strictly_before=True`` finds the last snapshot dated < cutoff (i.e. the
    period-start baseline = prior period's close). Returns None when the ticker
    has no snapshot in range (e.g. opened mid-period).
    """
    best: Optional[float] = None
    iso = cutoff.isoformat()
    for r in rows_by_ticker.get(ticker, []):
        d = r.get("date", "")
        if (d < iso) if strictly_before else (d <= iso):
            best = _f(r.get("value_eur"))
        else:
            break
    return best


def net_contributions_between(ticker: str, start: date, end: date) -> float:
    """Net cash put into ``ticker`` in ``[start, end)`` (buys +, sells -)."""
    total = 0.0
    for t in list_transactions():
        if t.ticker.upper() != ticker.upper() or not (start <= t.date < end):
            continue
        if t.action == "buy":
            total += t.quantity * t.price + t.fees
        elif t.action == "sell":
            total -= t.quantity * t.price - t.fees
    return total


def net_contributions(ticker: str, since: date) -> float:
    """Net cash put into ``ticker`` on/after ``since`` (buys +, sells -)."""
    return net_contributions_between(ticker, since, date.max)


def position_period_pnl(on: Optional[date] = None) -> dict:
    """Per-position month / YTD / all-time P&L + a portfolio total band.

    Reads only the daily history + ledger, so it is consistent with the Holdings
    table and the daily snapshot. Crypto + equities are unified (all EUR).
    """
    on = on or date.today()
    rows = positions_daily_rows()
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_ticker[r.get("ticker", "")].append(r)

    held = current_holdings()
    m_start, y_start = month_start(on), year_start(on)

    out_rows: list[dict] = []
    for ticker, qty in held.items():
        snaps = by_ticker.get(ticker, [])
        latest = snaps[-1] if snaps else None
        value = _f(latest.get("value_eur")) if latest else 0.0
        price = _f(latest.get("price_eur")) if latest else None
        basis = _f(latest.get("cost_basis_eur")) if latest else 0.0

        v_month = value_asof(by_ticker, ticker, m_start, strictly_before=True) or 0.0
        v_year = value_asof(by_ticker, ticker, y_start, strictly_before=True) or 0.0
        contrib_m = net_contributions(ticker, m_start)
        contrib_y = net_contributions(ticker, y_start)

        pnl_all = value - basis
        pnl_month = value - v_month - contrib_m
        pnl_ytd = value - v_year - contrib_y

        meta = get_position(ticker)
        out_rows.append({
            "ticker": ticker,
            "name": meta.name if meta else ticker,
            "type": meta.type if meta else None,
            "qty": round(qty, 8),
            "price_eur": round(price, 4) if price else None,
            "value_eur": round(value, 2),
            "cost_basis_eur": round(basis, 2),
            "pnl_all": round(pnl_all, 2),
            "pnl_all_pct": round(pnl_all / basis, 4) if basis > 1e-9 else None,
            "pnl_month": round(pnl_month, 2),
            "pnl_month_pct": round(pnl_month / (v_month + contrib_m), 4)
            if (v_month + contrib_m) > 1e-9 else None,
            "pnl_ytd": round(pnl_ytd, 2),
            "pnl_ytd_pct": round(pnl_ytd / (v_year + contrib_y), 4)
            if (v_year + contrib_y) > 1e-9 else None,
        })

    total_value = sum(r["value_eur"] for r in out_rows)
    for r in out_rows:
        r["weight"] = round(r["value_eur"] / total_value, 4) if total_value > 1e-9 else None
    out_rows.sort(key=lambda r: r["value_eur"], reverse=True)

    return {
        "positions": out_rows,
        "count": len(out_rows),
        "total_value": round(total_value, 2),
        "pnl_month_total": round(sum(r["pnl_month"] for r in out_rows), 2),
        "pnl_ytd_total": round(sum(r["pnl_ytd"] for r in out_rows), 2),
        "pnl_all_total": round(sum(r["pnl_all"] for r in out_rows), 2),
        "as_of": rows[-1].get("date") if rows else on.isoformat(),
    }


# --- net-worth daily series + decomposition ----------------------------------
def networth_daily(days: int = 90) -> list[dict]:
    """Last ``days`` rows of networth_daily.csv — **chart trend only**.

    Live-ledger-priced (see module docstring), not the authoritative net worth;
    the UI must caption this series as a trend line, never as "current net
    worth" — that figure is ``money.latest_net_worth()`` (Excel).
    """
    rows = sorted(read_rows(NETWORTH_DAILY_CSV), key=lambda r: r.get("date", ""))
    trimmed = rows[-days:] if days and len(rows) > days else rows
    return [
        {
            "date": r.get("date"),
            "net_worth_eur": _f(r.get("net_worth_eur")),
            "bank_total": _f(r.get("bank_total")),
            "portfolio_total_eur": _f(r.get("portfolio_total_eur")),
            "crypto_total_eur": _f(r.get("crypto_total_eur")),
        }
        for r in trimmed
    ]


def _nw_row_asof(rows: list[dict], cutoff: date, *, strictly_before: bool) -> Optional[dict]:
    best: Optional[dict] = None
    iso = cutoff.isoformat()
    for r in rows:
        d = r.get("date", "")
        if (d < iso) if strictly_before else (d <= iso):
            best = r
        else:
            break
    return best


def _savings_this_month(on: date) -> Optional[float]:
    """income - expenses for the current month from the Excel IvE sheet (None if absent)."""
    try:
        from modules.finance import money

        totals = money.monthly_totals()
    except Exception as exc:  # noqa: BLE001 — Excel may be missing/locked
        logger.warning("monthly_totals unavailable for decomposition: %s", exc)
        return None
    if totals is None or totals.empty or "month" not in totals.columns:
        return None
    key = f"{on.year:04d}-{on.month:02d}"
    match = totals[totals["month"].astype(str).str.startswith(key)]
    if match.empty:
        return None
    row = match.iloc[-1]
    inc, exp = row.get("income"), row.get("expenses")
    if inc is None or exp is None:
        return None
    try:
        return round(float(inc) - float(exp), 2)
    except (TypeError, ValueError):
        return None


def month_decomposition(on: Optional[date] = None) -> dict:
    """Split this month's net-worth change into savings vs market P&L.

    - **savings** (cash flow) = income - expenses (Excel IvE sheet; None if absent).
    - **investments** (market P&L) = Δ(portfolio+crypto value) - net contributions.
    - **net_contributions** = buys - sells across the depot (net-worth-neutral; shown
      as a labelled footnote, NOT added into the delta).

    savings + investments reconcile to the net-worth MoM delta (contributions net
    out). When the IvE sheet is unavailable, savings is derived as
    ``mom_delta - investments`` so the two still sum, and ``savings_source`` says so.

    ``mom_delta`` here is the live-ledger delta (see module docstring) — an
    analytical "what moved it" breakdown, not the headline MoM figure. The UI
    must caption it as such; the authoritative month-over-month net-worth
    change is the difference between the last two ``networth_history.history()``
    entries (Excel), which can legitimately differ from this one.
    """
    on = on or date.today()
    rows = sorted(read_rows(NETWORTH_DAILY_CSV), key=lambda r: r.get("date", ""))
    if not rows:
        return {"available": False, "reason": "no networth_daily.csv history yet"}

    m_start = month_start(on)
    latest = rows[-1]
    baseline = _nw_row_asof(rows, m_start, strictly_before=True) or rows[0]

    nw_now = _f(latest.get("net_worth_eur"))
    nw_start = _f(baseline.get("net_worth_eur"))
    mom_delta = round(nw_now - nw_start, 2)

    invest_now = _f(latest.get("portfolio_total_eur")) + _f(latest.get("crypto_total_eur"))
    invest_start = _f(baseline.get("portfolio_total_eur")) + _f(baseline.get("crypto_total_eur"))
    contributions = round(_net_contributions_all(m_start), 2)
    investments = round((invest_now - invest_start) - contributions, 2)

    savings = _savings_this_month(on)
    savings_source = "income_vs_expenses"
    if savings is None:
        # No IvE sheet -> back savings out of the identity so the two drivers tie.
        savings = round(mom_delta - investments, 2)
        savings_source = "derived (mom_delta - investments)"

    # In the ideal identity savings + investments == mom_delta (contributions net
    # out). With a real, monthly-stepped bank balance the measured savings can
    # diverge; expose the gap honestly instead of forcing reconciliation.
    residual = round(mom_delta - savings - investments, 2)

    return {
        "available": True,
        "month": f"{on.year:04d}-{on.month:02d}",
        "baseline_date": baseline.get("date"),
        "as_of": latest.get("date"),
        "net_worth_now": round(nw_now, 2),
        "net_worth_start": round(nw_start, 2),
        "mom_delta": mom_delta,
        "savings": savings,
        "savings_source": savings_source,
        "investments": investments,
        "net_contributions": contributions,
        "residual": residual,
        "bank_change": round(_f(latest.get("bank_total")) - _f(baseline.get("bank_total")), 2),
    }


def _net_contributions_all(since: date) -> float:
    """Net cash moved into the whole depot on/after ``since`` (buys + , sells -)."""
    total = 0.0
    for t in list_transactions():
        if t.date < since:
            continue
        if t.action == "buy":
            total += t.quantity * t.price + t.fees
        elif t.action == "sell":
            total -= t.quantity * t.price - t.fees
    return total
