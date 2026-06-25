"""Realized trade log — FIFO buy/sell matching -> data/realized_trades.csv.

Phase B § d "Trade log". Every SELL in ``transactions.jsonl`` is matched against
the oldest open BUY lots (FIFO, mirroring :func:`positions.cost_basis`) to
produce a row of *closed* trade economics:

    ticker, date_bought, date_sold, qty, buy_price_eur, sell_price_eur,
    fees_eur, realized_gain_eur, holding_days

- ``buy_price_eur`` is the lot's per-share cost **including** its allocated buy
  fees (same convention as the cost-basis FIFO).
- ``sell_price_eur`` is the gross sell price per share.
- ``fees_eur`` is the sell fee allocated to this matched slice (pro-rata by qty).
- ``realized_gain_eur = qty*(sell_price_eur - buy_price_eur) - fees_eur``.

The whole CSV is **rebuilt from the ledger** on each call (the ledger is the
source of truth), so it's idempotent and always consistent with transactions.
:func:`ytd_realized` then becomes a simple sum — relevant for German
Abgeltungsteuer planning.
"""
from __future__ import annotations

import logging
from datetime import date

from core.config import REALIZED_TRADES_CSV, get_logger
from modules.finance._csv_store import read_rows, write_rows
from modules.finance.positions import list_transactions

logger = get_logger(__name__)

REALIZED_COLUMNS = [
    "ticker", "date_bought", "date_sold", "qty",
    "buy_price_eur", "sell_price_eur", "fees_eur",
    "realized_gain_eur", "holding_days",
]


def compute_realized_trades() -> list[dict]:
    """FIFO-match all sells against buys across the ledger -> realized rows."""
    # Group quantity-moving transactions per ticker, in date order.
    by_ticker: dict[str, list] = {}
    for t in sorted(list_transactions(), key=lambda x: x.date):
        if t.action in ("buy", "sell"):
            by_ticker.setdefault(t.ticker, []).append(t)

    rows: list[dict] = []
    for ticker, txns in by_ticker.items():
        lots: list[dict] = []  # open buy lots: {qty, price (incl buy fees), date}
        for t in txns:
            if t.action == "buy":
                per_share = t.price + (t.fees / t.quantity if t.quantity else 0.0)
                lots.append({"qty": t.quantity, "price": per_share, "date": t.date})
                continue
            # SELL: consume oldest lots first; allocate sell fee pro-rata by qty.
            remaining = t.quantity
            sell_fee_per_share = (t.fees / t.quantity) if t.quantity else 0.0
            while remaining > 1e-9 and lots:
                lot = lots[0]
                take = min(lot["qty"], remaining)
                fees = round(sell_fee_per_share * take, 2)
                gain = take * (t.price - lot["price"]) - fees
                rows.append({
                    "ticker": ticker,
                    "date_bought": lot["date"].isoformat(),
                    "date_sold": t.date.isoformat(),
                    "qty": round(take, 8),
                    "buy_price_eur": round(lot["price"], 6),
                    "sell_price_eur": round(t.price, 6),
                    "fees_eur": fees,
                    "realized_gain_eur": round(gain, 2),
                    "holding_days": (t.date - lot["date"]).days,
                })
                lot["qty"] -= take
                remaining -= take
                if lot["qty"] <= 1e-9:
                    lots.pop(0)
            if remaining > 1e-9:
                logger.warning(
                    "%s: sell of %.8f exceeds open buy lots by %.8f (short/unmatched)",
                    ticker, t.quantity, remaining,
                )
    rows.sort(key=lambda r: (r["date_sold"], r["ticker"]))
    return rows


def rebuild_realized_trades() -> list[dict]:
    """Recompute and overwrite ``realized_trades.csv``. Returns the rows written."""
    rows = compute_realized_trades()
    write_rows(REALIZED_TRADES_CSV, rows, REALIZED_COLUMNS)
    logger.info("Wrote %d realized trade(s) to %s", len(rows), REALIZED_TRADES_CSV.name)
    return rows


def ytd_realized(year: int | None = None) -> float:
    """Sum of realized gains for trades sold in ``year`` (default: current year).

    Reads the persisted CSV (rebuild it first if the ledger changed).
    """
    year = year or date.today().year
    total = 0.0
    for r in read_rows(REALIZED_TRADES_CSV):
        sold = r.get("date_sold", "")
        if sold[:4] == f"{year:04d}":
            try:
                total += float(r.get("realized_gain_eur") or 0.0)
            except ValueError:
                continue
    return round(total, 2)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    rows = rebuild_realized_trades()
    logger.info("YTD realized (%d): EUR %.2f", date.today().year, ytd_realized())
    for r in rows:
        logger.info("%s", r)


if __name__ == "__main__":
    main()
