"""Backtesting + scenario endpoints (Phase 15c, Category G).

Counterfactual P&L plus market-shock and FX-shock scenario analysis. The shock
scenarios run against current holdings (the request only carries the shock
parameters).
"""
from __future__ import annotations

import warnings
from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from core.config import get_logger
from modules.finance import backtest as bt
from modules.finance.positions import current_holdings

logger = get_logger(__name__)

router = APIRouter()


class WhatIfRequest(BaseModel):
    ticker: str
    action: str = "hold"
    qty: float
    date: date


class MarketShockRequest(BaseModel):
    shock_pct: float


class FxShockRequest(BaseModel):
    currency: str
    shock_pct: float


@router.post("/backtest/what-if")
def what_if(req: WhatIfRequest) -> dict:
    """Counterfactual P&L for a hypothetical trade ('what if I had bought X')."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return bt.what_if_held(req.ticker.upper(), req.action, req.qty, req.date)


@router.post("/backtest/market-shock")
def market_shock(req: MarketShockRequest) -> dict:
    """Estimated portfolio impact of a market move (beta-scaled per position)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return bt.scenario_market_shock(current_holdings(), req.shock_pct)


@router.post("/backtest/fx-shock")
def fx_shock(req: FxShockRequest) -> dict:
    """Estimated portfolio impact of an FX move on positions in that currency."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return bt.scenario_fx_shock(current_holdings(), req.currency, req.shock_pct)
