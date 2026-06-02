"""Brinson performance attribution endpoint (Phase 15e, Category B S-priority)."""
from __future__ import annotations

import warnings

from fastapi import APIRouter, Query

from core.config import get_logger
from modules.finance import attribution

logger = get_logger(__name__)

router = APIRouter()


@router.get("/attribution/brinson")
def brinson(period: str = Query("ytd", pattern="^(ytd|1y|3y|5y|all)$")) -> dict:
    """Brinson allocation / selection / interaction over the four buckets."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return attribution.bucket_attribution(period=period)
