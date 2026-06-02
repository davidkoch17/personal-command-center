"""German tax calculations: Abgeltungsteuer, Spekulationsfrist (Phase 15d, J).

After-tax returns under German capital-gains rules:
- Equities/ETFs: Abgeltungsteuer 25% + Soli (and optional church tax).
- Crypto: tax-free after a 12-month holding period (§23 EStG Spekulationsfrist).
- Sparerpauschbetrag: €1,000/year tax-free allowance.
"""
from __future__ import annotations

from datetime import date


ABGELTUNGSTEUER = 0.25
SOLI = 0.055  # solidarity surcharge on Abgeltungsteuer
CHURCH_TAX_RATE = 0.09  # ~9% on Abgeltungsteuer, varies by state
# Effective rate (with Soli, no church): ~26.375%

SPARERPAUSCHBETRAG = 1000  # EUR tax-free allowance per year


def effective_tax_rate(church_tax: bool = False) -> float:
    """Combined capital-gains rate: Abgeltungsteuer + Soli (+ optional church)."""
    base = ABGELTUNGSTEUER
    with_soli = base * (1 + SOLI)
    if church_tax:
        with_soli += base * CHURCH_TAX_RATE
    return with_soli


def _plus_one_year(d: date) -> date:
    """``d`` one year later, clamping Feb-29 to Feb-28 in a non-leap year."""
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # 29 Feb -> 28 Feb
        return d.replace(year=d.year + 1, day=28)


def crypto_holding_period_status(buy_date: date, today: date | None = None) -> dict:
    """Check if a crypto holding has passed the 12-month Spekulationsfrist."""
    today = today or date.today()
    days_held = (today - buy_date).days
    days_to_tax_free = max(0, 365 - days_held)
    return {
        "days_held": days_held,
        "days_to_tax_free": days_to_tax_free,
        "is_tax_free": days_held >= 365,
        "tax_free_date": _plus_one_year(buy_date).isoformat(),
    }


def after_tax_return(gross_return: float, holding_period_days: int, asset_type: str,
                     church_tax: bool = False) -> float:
    """Compute after-tax return considering type + holding period."""
    if asset_type == "crypto" and holding_period_days >= 365:
        return gross_return  # Tax-free
    if gross_return < 0:
        return gross_return  # No tax on losses
    rate = effective_tax_rate(church_tax)
    return gross_return * (1 - rate)


def annual_tax_estimate(realized_gains: float, dividends: float,
                        church_tax: bool = False) -> dict:
    """Estimate annual tax owed considering Sparerpauschbetrag."""
    taxable_base = max(0, realized_gains + dividends - SPARERPAUSCHBETRAG)
    rate = effective_tax_rate(church_tax)
    tax_owed = taxable_base * rate
    return {
        "realized_gains": realized_gains,
        "dividends": dividends,
        "sparerpauschbetrag": SPARERPAUSCHBETRAG,
        "sparerpauschbetrag_used": min(SPARERPAUSCHBETRAG, max(0.0, realized_gains + dividends)),
        "taxable_base": taxable_base,
        "tax_owed": tax_owed,
        "effective_rate": rate,
    }


def holding_period_for_ticker(ticker: str, today: date | None = None) -> dict:
    """Spekulationsfrist status for a held crypto ticker from its earliest buy.

    Looks at the transaction log for the earliest ``buy`` lot. Returns
    ``available: False`` for names with no buy history.
    """
    from modules.finance.positions import get_position, transactions_for

    today = today or date.today()
    buys = [t for t in transactions_for(ticker) if t.action == "buy"]
    if not buys:
        return {"ticker": ticker, "available": False, "reason": "no buy transactions"}
    earliest = min(t.date for t in buys)
    meta = get_position(ticker)
    status = crypto_holding_period_status(earliest, today)
    return {
        "ticker": ticker,
        "available": True,
        "type": meta.type if meta else None,
        "is_crypto": (meta.type == "crypto") if meta else None,
        "earliest_buy_date": earliest.isoformat(),
        **status,
    }
