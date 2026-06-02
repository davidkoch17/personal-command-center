"""Four-bucket allocation endpoint (Phase 15a, Investment_Philosophy.md § 0)."""
from __future__ import annotations

import warnings

from fastapi import APIRouter

from core.config import get_logger
from modules.finance.buckets import bucket_allocation

logger = get_logger(__name__)

router = APIRouter()


@router.get("/buckets")
def buckets() -> dict:
    """Current 4-bucket allocation vs target, with drift + trigger alerts."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return bucket_allocation()
