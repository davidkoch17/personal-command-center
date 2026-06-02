"""Currency conversion + multi-currency reporting endpoints (Phase 15e, Cat. K).

Routes:
- ``GET /api/finance/currency/fx/{from_ccy}/{to_ccy}`` → current FX rate
- ``GET /api/finance/currency/breakdown``             → portfolio by currency
- ``GET /api/finance/currency/performance``           → performance in a reporting currency
"""
from __future__ import annotations

import warnings

import empyrical as ep
from fastapi import APIRouter, Query

from core.config import get_logger
from modules.finance import currency, performance as perf
from modules.finance.decision_support import current_positions_and_prices

logger = get_logger(__name__)

router = APIRouter()

_CCY = "^(EUR|USD)$"
_TRADING_DAYS = 252


@router.get("/currency/fx/{from_ccy}/{to_ccy}")
def fx_rate(from_ccy: str, to_ccy: str) -> dict:
    """Latest available FX rate for the ``from→to`` pair (None if unavailable)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rate = currency.get_fx_rate(from_ccy.upper(), to_ccy.upper())
    return {
        "from": from_ccy.upper(),
        "to": to_ccy.upper(),
        "rate": rate,
        "available": rate is not None,
    }


@router.get("/currency/breakdown")
def breakdown(currency_to: str = Query("EUR", alias="currency", pattern=_CCY)) -> dict:
    """Portfolio value split by each holding's native currency."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        positions, prices = current_positions_and_prices()
        # ``current_positions_and_prices`` omits currency; backfill from metadata.
        from modules.finance.positions import get_position
        for p in positions:
            meta = get_position(p["ticker"])
            p["currency"] = meta.currency if meta else "USD"
        return currency.position_currency_breakdown(positions, prices, currency_to)


@router.get("/currency/performance")
def performance_in_currency(
    period: str = Query("ytd", pattern="^(ytd|1y|3y|5y|all)$"),
    currency_to: str = Query("EUR", alias="currency", pattern=_CCY),
) -> dict:
    """Headline performance computed in the chosen reporting currency.

    Also returns the hedged-vs-unhedged decomposition so David can see how much
    of the return is the assets vs. EUR/USD drift.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        returns = currency.reporting_returns(currency_to)
        if returns.empty:
            return {"period": period, "currency": currency_to.upper(),
                    "available": False, "reason": "no priced holdings"}
        sliced = perf.filter_by_period(returns, period)

        # Native-currency base series for the hedged/unhedged split.
        positions, prices = current_positions_and_prices()
        from modules.finance.positions import get_position
        for p in positions:
            meta = get_position(p["ticker"])
            p["currency"] = meta.currency if meta else "USD"
            p["_value"] = p["quantity"] * prices.get(p["ticker"], 0)
        decomposition = currency.hedged_vs_unhedged(
            positions, perf.portfolio_returns(), currency_to
        )

        return {
            "period": period,
            "currency": currency_to.upper(),
            "available": True,
            "time_weighted_return": perf._f(ep.cum_returns_final(sliced)) if not sliced.empty else None,
            "annualized_return": perf._f(ep.annual_return(sliced, annualization=_TRADING_DAYS))
            if not sliced.empty else None,
            "volatility": perf._f(ep.annual_volatility(sliced, annualization=_TRADING_DAYS))
            if not sliced.empty else None,
            "hedged_vs_unhedged": decomposition,
        }
