"""German tax endpoints (Phase 15d, Category J).

Annual Abgeltungsteuer estimate, per-ticker Spekulationsfrist status, and an
after-tax-return helper. Pure calculations from ``modules.finance.tax``.
"""
from __future__ import annotations

import warnings

from fastapi import APIRouter
from pydantic import BaseModel

from core.config import get_logger
from modules.finance import tax

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
