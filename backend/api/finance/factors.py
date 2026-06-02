"""Fama-French factor analytics endpoints (Phase 15b, Category E)."""
from __future__ import annotations

import warnings

from fastapi import APIRouter, Query

from core.config import get_logger
from modules.finance import factors

logger = get_logger(__name__)

router = APIRouter()

_REGION = "^(US|Europe|Global)$"


@router.get("/factors/ff3")
def ff3(region: str = Query("US", pattern=_REGION)) -> dict:
    """Fama-French 3-factor regression on the current portfolio."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return factors.ff3_regression(region=region)


@router.get("/factors/decomposition")
def decomposition(region: str = Query("US", pattern=_REGION)) -> dict:
    """Variance decomposition across market / size / value / idiosyncratic."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return factors.factor_exposure_decomposition(region=region)


@router.get("/factors/ff5")
def ff5(region: str = Query("US", pattern=_REGION)) -> dict:
    """Fama-French 5-factor regression (adds RMW + CMA) — Phase 15e."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return factors.ff5_regression(region=region)


@router.get("/factors/momentum")
def momentum(region: str = Query("US", pattern=_REGION)) -> dict:
    """Carhart 4-factor regression (FF3 + UMD momentum) — Phase 15e."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return factors.momentum_factor(region=region)
