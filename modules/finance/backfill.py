"""History backfill for positions_daily.csv + networth_daily.csv (Phase B § d).

**LOCKED requirement** (build spec § d STORAGE): on first run, seed the
per-position daily history from yfinance daily-close history + a ledger replay,
so the Holdings tab's P&L month / YTD / all-time are correct from day 1 instead
of accruing over a year.

For every ticker ever traded, from its first buy date to today, this walks each
trading day in the EUR close series and reconstructs:

- ``qty``            — shares held that day (replay buys/sells up to the date),
- ``cost_basis_eur`` — FIFO basis of the lots open that day,
- ``price_eur``      — that day's close converted to EUR,
- ``value_eur``      — ``qty * price_eur``.

Rows are **upserted** into ``positions_daily.csv`` (key date+ticker), so it is
safe to re-run and it composes with the live daily snapshot. The net-worth
series is then seeded from those rows (portfolio = equities/ETFs, crypto =
crypto, bank = the month's ending balance from Finance_Tracker.xlsx, debts = 0).

Run:
    python -m modules.finance.backfill
"""
from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from core.config import NETWORTH_DAILY_CSV, POSITIONS_DAILY_CSV, get_logger
from modules.finance._csv_store import read_rows, upsert_rows
from modules.finance.currency import closes_eur
from modules.finance.daily_snapshot import (
    NETWORTH_DAILY_COLUMNS,
    POSITIONS_DAILY_COLUMNS,
    bank_total_asof,
)
from modules.finance.positions import (
    cost_basis,
    first_transaction_date,
    get_position,
    holdings_asof,
    list_transactions,
)

logger = get_logger(__name__)


def _traded_tickers() -> list[str]:
    """Every ticker that appears in the buy/sell ledger."""
    seen: list[str] = []
    for t in list_transactions():
        if t.action in ("buy", "sell") and t.ticker not in seen:
            seen.append(t.ticker)
    return seen


def backfill_positions() -> list[dict]:
    """Reconstruct per-position daily rows for every traded ticker. Returns rows.

    Only *upserts* rows for tickers currently in ``_traded_tickers()`` — if a
    ticker's last remaining transaction is deleted (see
    ``positions.delete_transaction``), its existing historical rows here are
    not purged. Harmless for net worth (nothing still holds/prices it going
    forward) but stale rows can linger; not handled by this step.
    """
    rows: list[dict] = []
    for ticker in _traded_tickers():
        start = first_transaction_date(ticker)
        if start is None:
            continue
        series = closes_eur(ticker)
        if series.empty:
            logger.warning("No EUR price history for %s; skipping backfill", ticker)
            continue
        series = series[series.index.date >= start]
        if series.empty:
            continue
        # Reindex onto a continuous daily calendar and forward-fill, so weekends,
        # a flaky yfinance day, or today's not-yet-posted bar carry the last mark
        # instead of dropping the position from that day's net-worth total.
        full_idx = pd.date_range(series.index.min(), series.index.max(), freq="D")
        series = series.reindex(full_idx).ffill()
        for ts, price_eur in series.items():
            if pd.isna(price_eur):
                continue
            d = ts.date() if hasattr(ts, "date") else ts
            qty = holdings_asof(d).get(ticker, 0.0)
            if qty <= 1e-9:
                continue  # not held that day (fully sold / pre-purchase)
            _, total_basis = cost_basis(ticker, as_of=d)
            rows.append({
                "date": d.isoformat(),
                "ticker": ticker,
                "qty": round(qty, 8),
                "price_eur": round(float(price_eur), 4),
                "value_eur": round(qty * float(price_eur), 2),
                "cost_basis_eur": total_basis,
            })
    upsert_rows(POSITIONS_DAILY_CSV, rows, POSITIONS_DAILY_COLUMNS, key_cols=["date", "ticker"])
    logger.info("Backfilled %d position-day row(s) for %d ticker(s)",
                len(rows), len(_traded_tickers()))
    return rows


def backfill_networth() -> list[dict]:
    """Seed ``networth_daily.csv`` from the per-position daily rows.

    portfolio = equities/ETFs value, crypto = crypto value (both summed per day);
    bank = that month's Finance_Tracker ending balance; debts = 0. Today's row is
    left for the live snapshot to refine (it still gets upserted here so a
    backfill-only run is also complete).
    """
    pos_rows = read_rows(POSITIONS_DAILY_CSV)
    if not pos_rows:
        return []

    # Aggregate position value per (date) split by crypto vs portfolio.
    by_date: dict[str, dict[str, float]] = {}
    for r in pos_rows:
        d = r["date"]
        try:
            value = float(r.get("value_eur") or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        meta = get_position(r["ticker"])
        bucket = "crypto" if (meta and meta.type == "crypto") else "portfolio"
        by_date.setdefault(d, {"portfolio": 0.0, "crypto": 0.0})[bucket] += value

    nw_rows: list[dict] = []
    for d, comp in sorted(by_date.items()):
        on_date = date.fromisoformat(d)
        bank_total = round(bank_total_asof(on_date), 2)
        portfolio = round(comp["portfolio"], 2)
        crypto = round(comp["crypto"], 2)
        net_worth = round(bank_total + portfolio + crypto, 2)
        nw_rows.append({
            "date": d,
            "bank_total": bank_total,
            "portfolio_total_eur": portfolio,
            "crypto_total_eur": crypto,
            "debts_total": 0.0,
            "net_worth_eur": net_worth,
        })
    upsert_rows(NETWORTH_DAILY_CSV, nw_rows, NETWORTH_DAILY_COLUMNS, key_cols=["date"])
    logger.info("Seeded %d net-worth day row(s)", len(nw_rows))
    return nw_rows


def run_backfill() -> dict:
    """Run the full history backfill (positions, then net worth)."""
    pos = backfill_positions()
    nw = backfill_networth()
    summary = {
        "position_day_rows": len(pos),
        "networth_day_rows": len(nw),
        "tickers": _traded_tickers(),
    }
    logger.info("Backfill complete: %s", summary)
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    result = run_backfill()
    logger.info("Done: %s", result)


if __name__ == "__main__":
    main()
