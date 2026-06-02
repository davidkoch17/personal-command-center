"""One-time migration: Finance_Tracker.xlsx snapshots -> transaction log.

Reads the ``Investments_TR`` and ``Investments_Crypto`` snapshot sheets and
reconstructs an *implied initial buy* for every distinct holding, so the new
transaction-driven data layer (``positions.py``) starts with David's current
positions already loaded. Also writes per-ticker metadata to ``positions.json``.

Reconstruction is deliberately simple: one buy per holding, dated at its earliest
snapshot, sized to its *latest* snapshot quantity (= the current holding), priced
at the earliest snapshot's price. Inter-snapshot quantity drift (dividend
reinvestment, rounding) is treated as noise and not modelled — later, real
transactions go in via the dashboard / voice.

Idempotent: a holding that already has transactions is skipped (mirrors the spec's
"initial buy … if no prior transaction exists"), so re-running won't duplicate.

Run once:  ``python -m modules.finance.migrate_from_excel``
"""
from __future__ import annotations

import math
from datetime import date

import pandas as pd

from core.config import get_logger
from modules.finance.loader import investments_tr, investments_crypto
from modules.finance.positions import (
    Position,
    Transaction,
    add_position,
    record_transaction,
    transactions_for,
)

logger = get_logger(__name__)

# Excel position/coin name (case-insensitive substring) -> ticker + metadata.
# Buckets follow Investment_Philosophy.md § 0. Prices in the workbook are EUR.
_HOLDING_MAP: dict[str, dict] = {
    "alphabet": {"ticker": "GOOGL", "name": "Alphabet (GOOGL)", "type": "equity",
                 "bucket": "single_stocks", "sector": "Communication Services",
                 "region": "US", "currency": "EUR"},
    "byd": {"ticker": "BYDDY", "name": "BYD (BYDDY)", "type": "equity",
            "bucket": "single_stocks", "sector": "Consumer Discretionary",
            "region": "China", "currency": "EUR"},
    "alibaba": {"ticker": "BABA", "name": "Alibaba (BABA)", "type": "equity",
                "bucket": "single_stocks", "sector": "Consumer Discretionary",
                "region": "China", "currency": "EUR"},
    "solana": {"ticker": "SOL", "name": "Solana (SOL)", "type": "crypto",
               "bucket": "crypto", "sector": "Crypto", "region": "Global",
               "currency": "EUR"},
    "sol": {"ticker": "SOL", "name": "Solana (SOL)", "type": "crypto",
            "bucket": "crypto", "sector": "Crypto", "region": "Global",
            "currency": "EUR"},
}


def _resolve(name: str) -> dict | None:
    n = str(name or "").lower()
    for key, meta in _HOLDING_MAP.items():
        if key in n:
            return meta
    return None


def _coerce_date(value) -> date:
    ts = pd.Timestamp(value)
    return ts.date()


def _snapshots(df: pd.DataFrame, name_col: str) -> dict[str, list[dict]]:
    """Group snapshot rows by resolved ticker -> [{date, qty, price, value}…]."""
    grouped: dict[str, list[dict]] = {}
    if df.empty or name_col not in df.columns:
        return grouped
    # Locate the EUR price/value columns (the € sign survives as raw bytes).
    price_col = next((c for c in df.columns if "price" in str(c).lower()), None)
    value_col = next((c for c in df.columns if "value" in str(c).lower()), None)
    for _, row in df.iterrows():
        meta = _resolve(row.get(name_col))
        if not meta:
            logger.warning("No ticker mapping for holding %r; skipped", row.get(name_col))
            continue
        qty = row.get("Quantity")
        if qty is None or (isinstance(qty, float) and math.isnan(qty)):
            continue
        price = row.get(price_col) if price_col else None
        value = row.get(value_col) if value_col else None
        # Crypto April snapshot has no price -> back it out from value / qty.
        if (price is None or (isinstance(price, float) and math.isnan(price))) and value and qty:
            price = float(value) / float(qty)
        grouped.setdefault(meta["ticker"], []).append({
            "date": _coerce_date(row.get("Snapshot Date")),
            "qty": float(qty),
            "price": float(price) if price is not None and not (isinstance(price, float) and math.isnan(price)) else 0.0,
            "value": float(value) if value is not None else None,
        })
    return grouped


def migrate() -> dict:
    """Run the migration. Returns a summary dict of what was written."""
    tr_snaps = _snapshots(investments_tr(), "Position")
    cr_snaps = _snapshots(investments_crypto(), "Coin")

    all_snaps: dict[str, list[dict]] = {}
    for src in (tr_snaps, cr_snaps):
        for ticker, rows in src.items():
            all_snaps.setdefault(ticker, []).extend(rows)

    written: list[str] = []
    skipped: list[str] = []

    for ticker, rows in all_snaps.items():
        meta = next(m for m in _HOLDING_MAP.values() if m["ticker"] == ticker)
        # Ensure metadata exists regardless of whether we add transactions.
        add_position(Position(
            ticker=meta["ticker"], name=meta["name"], type=meta["type"],
            bucket=meta["bucket"], sector=meta.get("sector"),
            region=meta.get("region"), currency=meta.get("currency", "EUR"),
        ))

        if transactions_for(ticker):
            skipped.append(ticker)
            continue

        rows_sorted = sorted(rows, key=lambda r: r["date"])
        first = rows_sorted[0]
        latest = rows_sorted[-1]
        record_transaction(Transaction(
            date=first["date"],
            ticker=ticker,
            action="buy",
            quantity=round(latest["qty"], 8),   # current holding
            price=round(first["price"], 6),       # implied entry price
            currency=meta.get("currency", "EUR"),
            fees=0.0,
            notes="Migrated from Finance_Tracker.xlsx (reconstructed initial position)",
        ))
        written.append(ticker)

    summary = {"written": written, "skipped": skipped,
               "tickers": sorted(all_snaps.keys())}
    logger.info("Migration complete: %s", summary)
    return summary


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    result = migrate()
    print("Migration summary:")
    print(f"  tickers found : {', '.join(result['tickers']) or '(none)'}")
    print(f"  transactions  : {', '.join(result['written']) or '(none new)'}")
    print(f"  skipped (had) : {', '.join(result['skipped']) or '(none)'}")
