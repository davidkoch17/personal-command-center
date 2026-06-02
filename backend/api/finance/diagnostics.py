"""Finance data-source diagnostics endpoint (Phase 15e, Section 4)."""
from __future__ import annotations

import warnings

from fastapi import APIRouter, Query

from core.config import get_logger
from modules.finance import diagnostics

logger = get_logger(__name__)

router = APIRouter()


@router.get("/diagnostics")
def finance_diagnostics(probe: bool = Query(False)) -> dict:
    """Health + cache-freshness of every finance data source.

    ``probe=true`` adds a live yfinance + FX hit (slower; off by default so the
    Settings panel can render instantly, then refetch with the probe on demand).
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return {"checks": diagnostics.run_all(probe_network=probe)}
