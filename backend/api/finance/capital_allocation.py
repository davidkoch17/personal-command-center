"""Capital allocation endpoint (Phase 15d, Category J — Section 3.2).

Suggests how to deploy deployable cash across underweight buckets to move the
allocation toward the Section 0 targets.
"""
from __future__ import annotations

import warnings

from fastapi import APIRouter

from core.config import get_logger
from modules.finance import capital_allocation as ca

logger = get_logger(__name__)

router = APIRouter()


@router.get("/capital-allocation/suggest")
def suggest(cash: float | None = None) -> dict:
    """Suggested deployment of cash (defaults to the Money tracker balance)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ca.suggest_deployment(cash)
