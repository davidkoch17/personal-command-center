"""Phase 15a finance router — bundles the sophisticated finance sub-routers.

Mounted in ``backend/main.py`` under the ``/api/finance`` prefix. The legacy
``/api/portfolio`` router (Excel snapshots) stays separate and untouched.

Routes:
- ``/api/finance/positions``           (GET, POST)
- ``/api/finance/transactions``        (GET, POST)
- ``/api/finance/holdings``            (GET)
- ``/api/finance/prices/{ticker}``     (GET)
- ``/api/finance/returns/{ticker}``    (GET)
- ``/api/finance/performance``         (GET)
- ``/api/finance/performance/cumulative`` (GET)
- ``/api/finance/performance/rolling`` (GET)
- ``/api/finance/risk``                (GET)
- ``/api/finance/risk/correlation``    (GET)
- ``/api/finance/buckets``             (GET)

Phase 15b (portfolio theory + factor analytics):
- ``/api/finance/optimization/frontier``        (GET)
- ``/api/finance/optimization/min-variance``    (GET)
- ``/api/finance/optimization/max-sharpe``      (GET)
- ``/api/finance/optimization/risk-parity``     (GET)
- ``/api/finance/optimization/black-litterman`` (POST)
- ``/api/finance/optimization/signals``         (GET)
- ``/api/finance/factors/ff3``                  (GET)
- ``/api/finance/factors/decomposition``        (GET)

Phase 15c (decision support + backtesting):
- ``/api/finance/decisions/size``               (POST)
- ``/api/finance/decisions/rebalance``          (GET)
- ``/api/finance/decisions/harvest``            (GET)
- ``/api/finance/decisions/alerts``             (GET)
- ``/api/finance/decisions/hypotheses-view``    (GET)
- ``/api/finance/decisions/summary``            (GET)
- ``/api/finance/backtest/what-if``             (POST)
- ``/api/finance/backtest/market-shock``        (POST)
- ``/api/finance/backtest/fx-shock``            (POST)
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.api.finance import (
    backtest,
    buckets,
    decisions,
    factors,
    optimization,
    performance,
    positions,
    prices,
    risk,
)

router = APIRouter()
router.include_router(positions.router)
router.include_router(prices.router)
router.include_router(performance.router)
router.include_router(risk.router)
router.include_router(buckets.router)
router.include_router(optimization.router)
router.include_router(factors.router)
router.include_router(decisions.router)
router.include_router(backtest.router)
