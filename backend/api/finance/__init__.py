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
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.api.finance import buckets, performance, positions, prices, risk

router = APIRouter()
router.include_router(positions.router)
router.include_router(prices.router)
router.include_router(performance.router)
router.include_router(risk.router)
router.include_router(buckets.router)
