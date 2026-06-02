"""Historical-shock stress-test endpoints (Phase 15e, Category G S-priority)."""
from __future__ import annotations

import warnings

from fastapi import APIRouter, HTTPException

from core.config import get_logger
from modules.finance import stress_tests as st

logger = get_logger(__name__)

router = APIRouter()


@router.get("/stress/shocks")
def list_shocks() -> dict:
    """The known historical-shock windows that can be replayed."""
    return {"shocks": st.HISTORICAL_SHOCKS}


@router.get("/stress/replay/{period_key}")
def replay(period_key: str) -> dict:
    """Replay the current portfolio through a named historical shock."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = st.replay_historical_period(period_key)
    if not result.get("available") and result.get("reason", "").startswith("unknown"):
        raise HTTPException(status_code=404, detail=result["reason"])
    return result


@router.get("/stress/replay-all")
def replay_all() -> dict:
    """Replay every known shock against the current portfolio."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return st.replay_all()
