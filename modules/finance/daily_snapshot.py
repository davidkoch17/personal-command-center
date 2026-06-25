"""Daily net-worth + per-position snapshot job (Phase B § c "Daily snapshot job").

Scheduled ~18:00 via Windows Task Scheduler (run_daily_snapshot.bat). Each run:

1. Prices every held ticker (yfinance close -> EUR), and computes its FIFO cost
   basis, writing one row per position to ``data/positions_daily.csv``
   (``date, ticker, qty, price_eur, value_eur, cost_basis_eur``). This
   per-position history is what makes the Holdings tab's P&L month / YTD columns
   computable.
2. Aggregates the net-worth identity and appends one row to
   ``data/networth_daily.csv``::

       net_worth_eur = bank_total + portfolio_total_eur + crypto_total_eur - debts_total

   where ``portfolio`` = equities/ETFs, ``crypto`` = crypto holdings, ``bank`` =
   latest cash balance from Finance_Tracker.xlsx, ``debts`` = 0 (none tracked).

**Idempotent:** both writers upsert on the date key (positions also on ticker),
so re-running on the same day overwrites that day's rows instead of appending.

Run:
    python -m modules.finance.daily_snapshot
"""
from __future__ import annotations

import logging
from datetime import date

from core.config import (
    NETWORTH_DAILY_CSV,
    POSITIONS_DAILY_CSV,
    get_logger,
)
from modules.finance._csv_store import read_rows, upsert_rows
from modules.finance.positions import cost_basis, current_holdings, get_position
from modules.finance.price_history import latest_price_eur

logger = get_logger(__name__)

POSITIONS_DAILY_COLUMNS = ["date", "ticker", "qty", "price_eur", "value_eur", "cost_basis_eur"]
NETWORTH_DAILY_COLUMNS = [
    "date", "bank_total", "portfolio_total_eur", "crypto_total_eur",
    "debts_total", "net_worth_eur",
]


# --- Bank cash (from Finance_Tracker.xlsx) ----------------------------------

def bank_month_history() -> dict[str, float]:
    """Monthly bank ending balances ``{YYYY-MM: balance}`` (empty on failure)."""
    try:
        from modules.finance.loader import bank
        b = bank()
    except Exception as exc:  # noqa: BLE001 — Excel may be missing/locked
        logger.warning("Bank sheet unavailable: %s", exc)
        return {}
    if b.empty or "Ending Balance (€)" not in b.columns or "Month" not in b.columns:
        return {}
    import pandas as pd

    out: dict[str, float] = {}
    for _, row in b.iterrows():
        month = str(row.get("Month") or "").strip()
        bal = row.get("Ending Balance (€)")
        if month[:7].count("-") == 1 and month[:4].isdigit() and pd.notna(bal) and bal != 0:
            try:
                out[month[:7]] = float(bal)
            except (TypeError, ValueError):
                continue
    return out


def bank_total_asof(on_date: date) -> float:
    """Bank balance for the month of ``on_date``, or the latest prior month (0 if none)."""
    hist = bank_month_history()
    if not hist:
        return 0.0
    target = f"{on_date.year:04d}-{on_date.month:02d}"
    candidates = [m for m in hist if m <= target]
    if candidates:
        return hist[max(candidates)]
    # Before the first recorded month — use the earliest known balance.
    return hist[min(hist)]


# --- Position snapshot -------------------------------------------------------

def compute_positions_today(on_date: date | None = None) -> list[dict]:
    """One row per current holding: qty, EUR price, EUR value, EUR cost basis."""
    on_date = on_date or date.today()
    rows: list[dict] = []
    for ticker, qty in current_holdings().items():
        lp = latest_price_eur(ticker)
        price_eur = round(lp.eur_price, 4) if lp else None
        value_eur = round((lp.eur_price * qty), 2) if lp else None
        _, total_basis = cost_basis(ticker)
        rows.append({
            "date": on_date.isoformat(),
            "ticker": ticker,
            "qty": round(qty, 8),
            "price_eur": price_eur if price_eur is not None else "",
            "value_eur": value_eur if value_eur is not None else "",
            "cost_basis_eur": total_basis,
        })
    return rows


def _split_value(rows: list[dict]) -> tuple[float, float]:
    """Split position rows into (portfolio_total_eur, crypto_total_eur)."""
    portfolio = 0.0
    crypto = 0.0
    for r in rows:
        try:
            value = float(r.get("value_eur") or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        meta = get_position(r["ticker"])
        if meta and meta.type == "crypto":
            crypto += value
        else:
            portfolio += value
    return round(portfolio, 2), round(crypto, 2)


def run_snapshot(on_date: date | None = None) -> dict:
    """Compute + persist today's per-position and net-worth snapshot rows."""
    on_date = on_date or date.today()
    iso = on_date.isoformat()

    pos_rows = compute_positions_today(on_date)
    upsert_rows(POSITIONS_DAILY_CSV, pos_rows, POSITIONS_DAILY_COLUMNS, key_cols=["date", "ticker"])

    portfolio_total, crypto_total = _split_value(pos_rows)
    bank_total = round(bank_total_asof(on_date), 2)
    debts_total = 0.0
    net_worth = round(bank_total + portfolio_total + crypto_total - debts_total, 2)

    nw_row = {
        "date": iso,
        "bank_total": bank_total,
        "portfolio_total_eur": portfolio_total,
        "crypto_total_eur": crypto_total,
        "debts_total": debts_total,
        "net_worth_eur": net_worth,
    }
    upsert_rows(NETWORTH_DAILY_CSV, [nw_row], NETWORTH_DAILY_COLUMNS, key_cols=["date"])

    # Keep the monthly net-worth store (Wealth-page trend) fresh too.
    try:
        from modules.finance.networth_history import record_snapshot
        record_snapshot(net_worth, components={
            "bank": bank_total, "portfolio": portfolio_total, "crypto": crypto_total,
        }, source="daily-snapshot")
    except Exception as exc:  # noqa: BLE001 — never let the side store break the job
        logger.warning("monthly net-worth store update skipped: %s", exc)

    summary = {**nw_row, "positions": len(pos_rows)}
    logger.info("Snapshot %s: %s", iso, summary)
    return summary


def latest_networth() -> dict | None:
    """Most recent ``networth_daily.csv`` row (None if the file is empty)."""
    rows = read_rows(NETWORTH_DAILY_CSV)
    return rows[-1] if rows else None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    result = run_snapshot()
    logger.info("Done: %s", result)


if __name__ == "__main__":
    main()
