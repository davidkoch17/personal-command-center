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

Phase 15d (ecosystem — journal + watchlist + money integration):
- ``/api/finance/journal/decision``             (POST)
- ``/api/finance/journal/decisions``            (GET)
- ``/api/finance/journal/decision/{filename}``  (GET)
- ``/api/finance/journal/{filename}/retrospective`` (POST)
- ``/api/finance/journal/hit-rate``             (GET)
- ``/api/finance/journal/anti-portfolio``       (GET, POST)
- ``/api/finance/watchlist/metrics``            (GET)
- ``/api/finance/watchlist/simulate-add``       (POST)
- ``/api/finance/tax/annual-estimate``          (POST)
- ``/api/finance/tax/holding-period/{ticker}``  (GET)
- ``/api/finance/tax/after-tax-return``         (GET)
- ``/api/finance/capital-allocation/suggest``   (GET)
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.api.finance import (
    backtest,
    buckets,
    capital_allocation,
    decisions,
    factors,
    journal,
    optimization,
    performance,
    positions,
    prices,
    risk,
    tax,
    watchlist_analytics,
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
router.include_router(journal.router)
router.include_router(watchlist_analytics.router)
router.include_router(tax.router)
router.include_router(capital_allocation.router)
