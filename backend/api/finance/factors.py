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
