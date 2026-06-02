"""Single-call Portfolio-workspace snapshot (Phase 15e, Section 3.2).

The Portfolio workspace previously fired holdings + buckets + performance + risk
+ currency breakdown as separate round-trips. This endpoint bundles them so the
first paint needs exactly one request. Each sub-block is computed independently
and failures are isolated (a flaky benchmark fetch can't blank the holdings),
returning a per-block ``error`` instead of a 500 for the whole page.
"""
from __future__ import annotations

import warnings

from fastapi import APIRouter, Query

from core.config import DEFAULT_BENCHMARK, get_logger
from modules.finance import currency, performance as perf, risk
from modules.finance.buckets import bucket_allocation
from modules.finance.decision_support import current_positions_and_prices, decision_summary

from backend.api.finance.positions import get_holdings

logger = get_logger(__name__)

router = APIRouter()


def _safe(name: str, fn):
    """Run a snapshot sub-block, isolating its failure to a per-block error."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — one block must not break the page
        logger.warning("full-snapshot block '%s' failed: %s", name, exc)
        return {"error": str(exc)}


@router.get("/portfolio/full-snapshot")
def full_snapshot(
    period: str = Query("ytd", pattern="^(ytd|1y|3y|5y|all)$"),
    benchmark: str = Query(DEFAULT_BENCHMARK),
    currency_to: str = Query("EUR", alias="currency", pattern="^(EUR|USD)$"),
) -> dict:
    """Everything the Portfolio workspace needs for first paint, in one call."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        def _breakdown():
            positions, prices = current_positions_and_prices()
            from modules.finance.positions import get_position
            for p in positions:
                meta = get_position(p["ticker"])
                p["currency"] = meta.currency if meta else "USD"
            return currency.position_currency_breakdown(positions, prices, currency_to)

        return {
            "period": period,
            "benchmark": benchmark,
            "currency": currency_to.upper(),
            "holdings": _safe("holdings", get_holdings),
            "buckets": _safe("buckets", bucket_allocation),
            "performance": _safe("performance", lambda: perf.compute_all(period=period, benchmark=benchmark)),
            "risk": _safe("risk", lambda: risk.compute_all(benchmark=benchmark)),
            "currency_breakdown": _safe("currency_breakdown", _breakdown),
            "decision_summary": _safe("decision_summary", decision_summary),
        }
