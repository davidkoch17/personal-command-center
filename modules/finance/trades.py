"""Manual transaction entry (Phase B § c "Manual transaction entry").

Thin orchestration over the existing append-only ledger: the Holdings form
(built in Phase D) and any script call land here. Recording a trade:

1. appends the buy/sell to ``data/transactions.jsonl`` (via
   :func:`positions.record_transaction`),
2. recomputes the FIFO holdings + cost basis for the ticker, and
3. rebuilds ``data/realized_trades.csv`` so the trade log + YTD-realized figure
   stay in sync with the ledger.

Returns a summary dict the UI can show as confirmation. The ledger is the source
of truth; everything else is derived, so this never holds extra state.
"""
from __future__ import annotations

import logging
from datetime import date as date_cls
from typing import Optional

from core.config import get_logger
from modules.finance.positions import (
    Transaction,
    cost_basis,
    current_holdings,
    record_transaction,
)
from modules.finance.realized import rebuild_realized_trades, ytd_realized

logger = get_logger(__name__)


def record_trade(
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    *,
    fees: float = 0.0,
    currency: str = "EUR",
    trade_date: Optional[date_cls] = None,
    notes: Optional[str] = None,
) -> dict:
    """Record a manual buy/sell, then recompute FIFO cost basis + realized log.

    ``side`` is ``"buy"`` or ``"sell"``. Returns ``{ticker, holdings, avg_cost,
    total_basis, realized_count, ytd_realized}``.
    """
    side = side.lower().strip()
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    txn = Transaction(
        date=trade_date or date_cls.today(),
        ticker=ticker.upper().strip(),
        action=side,
        quantity=float(quantity),
        price=float(price),
        currency=currency.upper(),
        fees=float(fees),
        notes=notes,
    )
    record_transaction(txn)

    avg_cost, total_basis = cost_basis(txn.ticker)
    realized = rebuild_realized_trades()
    held = current_holdings().get(txn.ticker, 0.0)

    summary = {
        "ticker": txn.ticker,
        "side": side,
        "quantity": txn.quantity,
        "holdings": round(held, 8),
        "avg_cost": avg_cost,
        "total_basis": total_basis,
        "realized_count": len(realized),
        "ytd_realized": ytd_realized(),
    }
    logger.info("Recorded trade: %s", summary)
    return summary


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="Record a manual buy/sell transaction")
    p.add_argument("ticker")
    p.add_argument("side", choices=["buy", "sell"])
    p.add_argument("quantity", type=float)
    p.add_argument("price", type=float)
    p.add_argument("--fees", type=float, default=0.0)
    p.add_argument("--currency", default="EUR")
    p.add_argument("--date", dest="trade_date", default=None, help="YYYY-MM-DD (default today)")
    p.add_argument("--notes", default=None)
    args = p.parse_args()
    td = date_cls.fromisoformat(args.trade_date) if args.trade_date else None
    result = record_trade(
        args.ticker, args.side, args.quantity, args.price,
        fees=args.fees, currency=args.currency, trade_date=td, notes=args.notes,
    )
    logger.info("Done: %s", result)


if __name__ == "__main__":
    main()
