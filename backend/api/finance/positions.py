"""Positions / transactions / holdings endpoints (Phase 15a + Phase D)."""
from __future__ import annotations

import warnings

from fastapi import APIRouter, HTTPException, Query

from core.config import get_logger
from modules.finance import period_pnl, positions as pos
from modules.finance import realized
from modules.finance import risk
from modules.finance.price_history import get_returns, latest_price_eur
from modules.finance.positions import Position, Transaction

logger = get_logger(__name__)

router = APIRouter()


@router.get("/positions")
def get_positions() -> dict:
    """List all position metadata."""
    items = [p.model_dump() for p in pos.list_positions()]
    return {"positions": items, "count": len(items)}


@router.post("/positions")
def post_position(position: Position) -> dict:
    """Add (or replace) a position's metadata."""
    pos.add_position(position)
    return {"ok": True, "ticker": position.ticker}


@router.get("/transactions")
def get_transactions(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    ticker: str | None = Query(None),
) -> dict:
    """List transactions (newest first), paginated; optional ticker filter."""
    txns = pos.transactions_for(ticker) if ticker else pos.list_transactions()
    txns = sorted(txns, key=lambda t: t.date, reverse=True)
    total = len(txns)
    page = txns[offset: offset + limit]
    return {
        "transactions": [
            {**t.model_dump(), "date": t.date.isoformat()} for t in page
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/transactions")
def post_transaction(transaction: Transaction) -> dict:
    """Record a buy / sell / dividend / etc. to the append-only log."""
    try:
        pos.record_transaction(transaction)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to record transaction")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "ticker": transaction.ticker, "action": transaction.action}


@router.get("/holdings")
def get_holdings() -> dict:
    """Current holdings enriched with cost basis, live price + per-position risk.

    Per-position Sharpe / volatility / beta come from each ticker's own daily
    return history (cached). Weight is market-value share of the portfolio.
    """
    holdings = pos.current_holdings()
    rows: list[dict] = []
    market_values: dict[str, float] = {}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for ticker, qty in holdings.items():
            meta = pos.get_position(ticker)
            avg_cost, total_basis = pos.cost_basis(ticker)
            # latest_price_eur converts the native (USD) quote to EUR so that
            # market value and P&L line up with the EUR cost basis.
            lp = latest_price_eur(ticker)
            price = lp.eur_price if lp else None
            market_value = (price or 0.0) * qty
            market_values[ticker] = market_value
            rets = get_returns(ticker)
            rows.append({
                "ticker": ticker,
                "name": meta.name if meta else ticker,
                "type": meta.type if meta else None,
                "bucket": meta.bucket if meta else None,
                "currency": meta.currency if meta else "USD",
                "quantity": round(qty, 8),
                "avg_cost": avg_cost,
                "total_basis": total_basis,
                "current_price": round(price, 4) if price is not None else None,
                "price_currency": "EUR",
                "native_currency": lp.native_currency if lp else None,
                "native_price": round(lp.native_price, 4) if lp else None,
                "fx_rate": round(lp.fx_rate, 6) if lp else None,
                "fx_stale": lp.fx_stale if lp else None,
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(market_value - total_basis, 2) if price is not None else None,
                "unrealized_pnl_pct": round((market_value - total_basis) / total_basis, 4)
                if (price is not None and total_basis) else None,
                "sharpe": risk.sharpe(rets),
                "volatility": risk.annualized_vol(rets),
                "beta": risk.beta_vs(rets, "^GSPC"),
            })

    total_mv = sum(market_values.values())
    for r in rows:
        r["weight"] = round(market_values[r["ticker"]] / total_mv, 4) if total_mv > 0 else None

    rows.sort(key=lambda r: r["market_value"], reverse=True)
    return {"holdings": rows, "total_market_value": round(total_mv, 2), "count": len(rows)}


# --- Phase D: Holdings tab (period P&L + trade log) + Overview (net worth) ----

@router.get("/holdings/pnl")
def holdings_pnl() -> dict:
    """Per-position P&L split month / YTD / all-time + the total-band figures.

    Derived from positions_daily.csv + the ledger (contributions-adjusted), so the
    Holdings table's month/YTD columns line up with the daily snapshot history.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return period_pnl.position_period_pnl()


@router.get("/trades/realized")
def realized_trades() -> dict:
    """Closed-trade log (FIFO buy/sell matches) + the YTD realized total (Abgeltungsteuer)."""
    rows = realized.rebuild_realized_trades()
    rows.sort(key=lambda r: (r.get("date_sold", ""), r.get("ticker", "")), reverse=True)
    return {
        "trades": rows,
        "count": len(rows),
        "ytd_realized_eur": realized.ytd_realized(),
        "year": __import__("datetime").date.today().year,
    }


@router.get("/networth/daily")
def networth_daily(days: int = Query(90, ge=1, le=3650)) -> dict:
    """Daily net-worth series for the Overview sparkline (default last 90 days).

    Chart/trend data only, live-ledger-priced — NOT the authoritative net
    worth (that's ``GET /api/money/snapshot``, Excel-sourced). See
    ``modules.finance.period_pnl`` module docstring for why they can diverge.
    """
    series = period_pnl.networth_daily(days)
    return {"series": series, "count": len(series), "days": days}


@router.get("/networth/decomposition")
def networth_decomposition() -> dict:
    """This-month net-worth change split into savings vs market P&L (contributions netted).

    Live-ledger-priced analytics, not the authoritative net-worth headline —
    see ``GET /api/money/snapshot`` for that and ``period_pnl.py`` for why.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return period_pnl.month_decomposition()
