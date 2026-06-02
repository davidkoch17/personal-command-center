"""Backtesting + counterfactuals + scenario analysis.

Phase 15c, Category G. Counterfactual P&L ("what if I had held / bought X") plus
scenario stress tests (market shock via beta, FX shock). Sits on the 15a
price-history layer; every function degrades to an ``{"error": ...}`` dict rather
than raising when data is missing.
"""
from __future__ import annotations

from datetime import date

from modules.finance.positions import get_position
from modules.finance.price_history import get_price_on, get_returns
from modules.finance.risk import beta_vs


def what_if_held(ticker: str, action: str, qty: float, action_date: date) -> dict:
    """What if instead of [action] I had held? Or what if I had bought X earlier?

    Counterfactual P&L calculation.
    """
    history = get_returns(ticker)
    if history.empty:
        return {"error": "no data"}

    today = date.today()
    period_returns = history.loc[str(action_date):str(today)]
    cumulative_return = float((1 + period_returns).prod() - 1)

    # Approximation: if we had bought qty at action_date, current value vs cost
    initial_price = get_price_on(ticker, action_date)
    current_price = get_price_on(ticker, today)
    if not initial_price or not current_price:
        return {"error": "no price data"}

    counterfactual_pnl = (current_price - initial_price) * qty
    return {
        "ticker": ticker,
        "action": action,
        "action_date": action_date.isoformat(),
        "initial_price": initial_price,
        "current_price": current_price,
        "qty": qty,
        "counterfactual_pnl": counterfactual_pnl,
        "cumulative_return_pct": cumulative_return * 100,
    }


def scenario_market_shock(portfolio: dict, shock_pct: float) -> dict:
    """If market drops by shock_pct (e.g. -0.20), what happens to portfolio?
    Uses beta to estimate per-position impact.
    """
    today = date.today()
    total_impact = 0.0
    total_value = 0.0
    per_position = {}
    for ticker, qty in portfolio.items():
        try:
            beta = beta_vs(get_returns(ticker), "^GSPC")
            price = get_price_on(ticker, today)
            if beta is None or price is None:
                per_position[ticker] = {"error": "no data"}
                continue
            value = qty * price
            position_impact = value * beta * shock_pct
            per_position[ticker] = {
                "beta": beta,
                "value": value,
                "impact": position_impact,
            }
            total_impact += position_impact
            total_value += value
        except Exception:  # noqa: BLE001
            per_position[ticker] = {"error": "no data"}

    return {
        "shock_pct": shock_pct,
        "total_value": total_value,
        "total_estimated_impact": total_impact,
        "impact_pct": (total_impact / total_value) if total_value else None,
        "per_position": per_position,
    }


def scenario_fx_shock(portfolio: dict, currency: str, shock_pct: float) -> dict:
    """If [currency] moves by shock_pct, what happens?

    Identifies positions denominated in ``currency`` (from each ticker's position
    metadata) and applies the move to their full market value. A position's
    reporting/native currency is read from ``positions.json``; positions in other
    currencies are unaffected.
    """
    today = date.today()
    affected = {}
    total = 0.0
    total_exposure = 0.0
    cur = currency.upper()
    for ticker, qty in portfolio.items():
        meta = get_position(ticker)
        pos_currency = (meta.currency if meta else "USD").upper()
        if pos_currency != cur:
            continue
        price = get_price_on(ticker, today)
        if price is None:
            affected[ticker] = {"error": "no data"}
            continue
        value = qty * price
        impact = value * shock_pct
        affected[ticker] = {"currency": pos_currency, "value": value, "impact": impact}
        total += impact
        total_exposure += value
    return {
        "currency": cur,
        "shock_pct": shock_pct,
        "total_impact": total,
        "total_exposure": total_exposure,
        "affected": affected,
    }
