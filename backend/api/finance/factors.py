"""Fama-French factor analytics endpoints (Phase 15b, Category E)."""
from __future__ import annotations

import warnings

from fastapi import APIRouter, Query

from core.config import DEFAULT_BENCHMARK, get_logger
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


# --- Chunk 8: rolling betas + portfolio-vs-benchmark loadings -------------------------------

@router.get("/factors/rolling")
def rolling(
    region: str = Query("US", pattern=_REGION),
    model: str = Query("ff3", pattern="^(ff3|ff5)$"),
    window: int = Query(36, ge=12, le=120),
) -> dict:
    """Rolling-window factor betas (default 36 months): MKT/SMB/HML, plus RMW/CMA for ff5."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return factors.portfolio_rolling_factor_betas(region=region, model=model, window_months=window)


@router.get("/factors/loadings-comparison")
def loadings_comparison(
    region: str = Query("US", pattern=_REGION),
    model: str = Query("ff3", pattern="^(ff3|ff5)$"),
    benchmark: str = Query(DEFAULT_BENCHMARK),
    period: str = Query("all", pattern="(?i)^(1y|3y|5y|all)$"),
) -> dict:
    """Portfolio and the selected comparison benchmark regressed on the same factors over the same months."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return factors.factor_loadings_comparison(benchmark=benchmark, region=region, period=period.lower(), model=model)
