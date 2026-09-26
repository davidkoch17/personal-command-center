"""Phase 15a finance router — bundles the sophisticated finance sub-routers.

Mounted in ``backend/main.py`` under the ``/api/finance`` prefix. The legacy
``/api/portfolio`` router (Excel snapshots) stays separate and untouched.

Routes:
- ``/api/finance/positions``           (GET, POST)
- ``/api/finance/transactions``        (GET, POST, PATCH /{id}, DELETE /{id})
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

Phase 15e (polish — currency + S-priority items + performance + diagnostics):
- ``/api/finance/currency/fx/{from}/{to}``       (GET)
- ``/api/finance/currency/breakdown``            (GET)
- ``/api/finance/currency/performance``          (GET)
- ``/api/finance/attribution/brinson``           (GET)
- ``/api/finance/factors/ff5``                   (GET)
- ``/api/finance/factors/momentum``              (GET)
- ``/api/finance/stress/shocks``                 (GET)
- ``/api/finance/stress/replay/{period_key}``    (GET)
- ``/api/finance/stress/replay-all``             (GET)
- ``/api/finance/portfolio/full-snapshot``       (GET)
- ``/api/finance/diagnostics``                   (GET)

Chunk 2 (Portfolio-tab dashboard):
- ``/api/finance/dashboard/summary``             (GET)
- ``/api/finance/dashboard/performance-indexed`` (GET)

Chunk 4 (Single Stock tab):
- ``/api/finance/stock-universe``                (GET)
- ``/api/finance/stock-detail/{ticker}``         (GET)
- ``/api/finance/peers/{ticker}``                (GET, PATCH)

Chunk 7 (forward what-if + security-level rebalance + quarterly cadence):
- ``/api/finance/scenarios/forward-whatif``      (POST)
- ``/api/finance/decisions/rebalance``           (GET, now with security_level_pairs)

Chunk 6 (tranche tracker + CAPM views):
- ``/api/finance/deployment-plans``              (GET, POST)
- ``/api/finance/deployment-plans/{id}``         (GET, PATCH, DELETE)
- ``/api/finance/deployment-plans/{id}/tranches/{index}/execute`` (POST)
- ``/api/finance/performance/sml``               (GET)
- ``/api/finance/performance/capm-decomposition`` (GET)

Chunk 5 (Benchmarks tab):
- ``/api/finance/benchmarks/compare``            (GET)
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.api.finance import (
    attribution,
    backtest,
    benchmarks,
    buckets,
    capital_allocation,
    currency,
    dashboard,
    decisions,
    deployment_plans,
    diagnostics,
    factors,
    forward_whatif,
    journal,
    optimization,
    performance,
    positions,
    prices,
    risk,
    snapshot,
    stock_detail,
    stress_tests,
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
# Phase 15e — currency, Brinson attribution, stress tests, full snapshot, diagnostics.
router.include_router(currency.router)
router.include_router(attribution.router)
router.include_router(stress_tests.router)
router.include_router(snapshot.router)
router.include_router(diagnostics.router)
# Chunk 2 — Portfolio-tab dashboard summary + indexed performance chart.
router.include_router(dashboard.router)
# Chunk 4 — Single Stock tab: fundamentals / position / price series / peers.
router.include_router(stock_detail.router)
# Chunk 5 — Benchmarks tab: metrics + correlation + indexed series in one call.
router.include_router(benchmarks.router)
# Chunk 6 — 50/30/20 deployment tranche tracker.
router.include_router(deployment_plans.router)
# Chunk 7 — forward EUR what-if simulator.
router.include_router(forward_whatif.router)
