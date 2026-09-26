"""Forward EUR what-if endpoint (Chunk 7, D5)."""
from __future__ import annotations

import warnings

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config import DEFAULT_BENCHMARK, get_logger
from modules.finance import forward_whatif as fw

logger = get_logger(__name__)

router = APIRouter()


class ForwardWhatIfRequest(BaseModel):
    ticker: str
    action: str  # "buy" | "sell"
    eur_amount: float
    benchmark: str = DEFAULT_BENCHMARK  # CAPM market for the forward Sharpe (shared useBenchmark)


@router.post("/scenarios/forward-whatif")
def forward_whatif(req: ForwardWhatIfRequest) -> dict:
    """Simulate buying/selling ``eur_amount`` EUR of ``ticker``: bucket allocation + drift,
    Sharpe/Sortino/vol deltas, the bucket a buy maps to, and cap/concentration warnings.
    422 with a plain-language message for trades that can't be simulated (e.g. selling
    something you don't own)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return fw.simulate_forward_trade(req.ticker, req.action, req.eur_amount, req.benchmark)
    except fw.WhatIfError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
