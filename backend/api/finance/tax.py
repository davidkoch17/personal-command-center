"""German tax endpoints (Phase 15d Category J; Chunk 9 Anlage-KAP extensions).

Annual Abgeltungsteuer estimate, per-ticker Spekulationsfrist status, an
after-tax-return helper (Phase 15d), and the Chunk 9 additions: a structured
Anlage-KAP preview, the Aktien/Sonstige/§23 loss-offset pots, and the
Vorabpauschale on thesaurierend ETFs. Pure calculations from
``modules.finance.tax`` / ``kap_form`` / ``verlustverrechnung`` / ``vorabpauschale``.
"""
from __future__ import annotations

import warnings
from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel

from core.config import get_logger
from modules.finance import kap_form, tax, verlustverrechnung, vorabpauschale

logger = get_logger(__name__)

router = APIRouter()


class AnnualEstimateRequest(BaseModel):
    realized_gains: float
    dividends: float = 0.0
    church_tax: bool = False


@router.post("/tax/annual-estimate")
def annual_estimate(req: AnnualEstimateRequest) -> dict:
    """Estimate annual capital-gains tax owed (with Sparerpauschbetrag)."""
    return tax.annual_tax_estimate(req.realized_gains, req.dividends, req.church_tax)


@router.get("/tax/holding-period/{ticker}")
def holding_period(ticker: str) -> dict:
    """Spekulationsfrist (12-month) status for a held crypto ticker."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return tax.holding_period_for_ticker(ticker.upper())


@router.get("/tax/after-tax-return")
def after_tax_return(gross_return: float, holding_period_days: int,
                     asset_type: str, church_tax: bool = False) -> dict:
    """After-tax return for a gross return, given asset type + holding period."""
    net = tax.after_tax_return(gross_return, holding_period_days, asset_type, church_tax)
    return {
        "gross_return": gross_return,
        "after_tax_return": net,
        "asset_type": asset_type,
        "holding_period_days": holding_period_days,
        "tax_free": asset_type == "crypto" and holding_period_days >= 365,
        "effective_rate": tax.effective_tax_rate(church_tax),
    }


# --- Chunk 9: Anlage KAP summary, loss-offset pots, Vorabpauschale --------------------------

@router.get("/tax/kap-summary")
def kap_summary(
    year: int = Query(default_factory=lambda: date.today().year),
    sparerpauschbetrag: float | None = Query(None, ge=0),
) -> dict:
    """Structured Anlage-KAP preview — not an Elster filing, see the disclaimer field."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return kap_form.kap_summary(tax_year=year, sparerpauschbetrag=sparerpauschbetrag)


@router.get("/tax/loss-pots")
def loss_pots(year: int = Query(default_factory=lambda: date.today().year)) -> dict:
    """Aktien / Sonstige / Spekulation-§23 Verlustverrechnungstopf balances."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return verlustverrechnung.current_pots(tax_year=year)


class CarryforwardUpdate(BaseModel):
    aktien: float | None = None
    sonstige: float | None = None
    spekulation_23: float | None = None


@router.get("/tax/loss-pots/carryforward")
def get_carryforward() -> dict:
    """The persisted manual prior-year carryforward per pot."""
    return verlustverrechnung.get_carryforwards()


@router.put("/tax/loss-pots/carryforward")
def set_carryforward(req: CarryforwardUpdate) -> dict:
    """Set (merge) the manual prior-year carryforward — David's own entry, we
    don't have the ledger history to compute it."""
    values = req.model_dump(exclude_none=True)
    return verlustverrechnung.set_carryforwards(values)


@router.get("/tax/vorabpauschale")
def vorabpauschale_summary(year: int = Query(default_factory=lambda: date.today().year)) -> dict:
    """Per-ETF Vorabpauschale on thesaurierend etf_foundation holdings."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return vorabpauschale.compute_for_year(tax_year=year)
