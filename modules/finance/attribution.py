"""Brinson performance attribution (Phase 15e, Category B S-priority).

Decomposes the portfolio's excess return over a benchmark into the three classic
Brinson-Hood-Beebower effects:

- **Allocation** — value added by over/under-weighting segments that out/under-
  performed the benchmark:  ``Σ (w_p − w_b) · r_b``
- **Selection** — value added by picking better-than-benchmark holdings *within*
  each segment:  ``Σ w_b · (r_p − r_b)``
- **Interaction** — the cross term:  ``Σ (w_p − w_b) · (r_p − r_b)``

:func:`brinson_attribution` is the pure formula (easy to unit-test).
:func:`bucket_attribution` is the live wrapper that segments the portfolio by its
four buckets, using each bucket's value-weighted holding return as ``r_p`` and a
per-bucket benchmark proxy as ``r_b``.
"""
from __future__ import annotations

from typing import Optional

import empyrical as ep

from core.config import BUCKET_LABELS, BUCKET_TARGETS, DEFAULT_BENCHMARK, BENCHMARKS, get_logger
from modules.finance.performance import filter_by_period
from modules.finance.positions import current_holdings, get_position
from modules.finance.price_history import get_closes, get_returns

logger = get_logger(__name__)

# Benchmark proxy per bucket — what an index-tracking version of that sleeve
# would have returned. Crypto benchmarks to BTC; the rest to the broad market.
_BUCKET_BENCHMARK = {
    "etf_foundation": BENCHMARKS[DEFAULT_BENCHMARK]["ticker"],
    "single_stocks": BENCHMARKS[DEFAULT_BENCHMARK]["ticker"],
    "crypto": "BTC-USD",
    "wild_cards": BENCHMARKS[DEFAULT_BENCHMARK]["ticker"],
}


def brinson_attribution(
    portfolio_weights: dict,
    benchmark_weights: dict,
    portfolio_segment_returns: dict,
    benchmark_segment_returns: dict,
) -> dict:
    """Pure Brinson decomposition over a common set of segments.

    All four dicts are keyed by segment. Missing keys default to 0. Returns the
    allocation / selection / interaction effects per segment plus their totals
    and the total excess return they sum to.
    """
    segments = (
        set(portfolio_weights)
        | set(benchmark_weights)
        | set(portfolio_segment_returns)
        | set(benchmark_segment_returns)
    )
    per_segment: dict[str, dict] = {}
    alloc_total = selection_total = interaction_total = 0.0
    for seg in segments:
        wp = portfolio_weights.get(seg, 0.0)
        wb = benchmark_weights.get(seg, 0.0)
        rp = portfolio_segment_returns.get(seg, 0.0)
        rb = benchmark_segment_returns.get(seg, 0.0)
        allocation = (wp - wb) * rb
        selection = wb * (rp - rb)
        interaction = (wp - wb) * (rp - rb)
        alloc_total += allocation
        selection_total += selection
        interaction_total += interaction
        per_segment[seg] = {
            "portfolio_weight": wp,
            "benchmark_weight": wb,
            "portfolio_return": rp,
            "benchmark_return": rb,
            "allocation": allocation,
            "selection": selection,
            "interaction": interaction,
            "total": allocation + selection + interaction,
        }
    total_excess = alloc_total + selection_total + interaction_total
    return {
        "per_segment": per_segment,
        "allocation_effect": alloc_total,
        "selection_effect": selection_total,
        "interaction_effect": interaction_total,
        "total_excess_return": total_excess,
    }


def _period_return(ticker: str, period: str) -> Optional[float]:
    """Cumulative return of a ticker over a named period (None if no data)."""
    rets = filter_by_period(get_returns(ticker), period)
    if rets.empty:
        return None
    return float(ep.cum_returns_final(rets))


def bucket_attribution(period: str = "ytd") -> dict:
    """Live Brinson attribution segmenting the portfolio by its four buckets.

    Portfolio weights are current bucket value shares; benchmark weights are the
    Section 0 bucket targets. Each bucket's ``r_p`` is its value-weighted holding
    return over ``period``; ``r_b`` is the bucket's benchmark proxy return.
    """
    holdings = current_holdings()
    if not holdings:
        return {"available": False, "reason": "no holdings"}

    # Value + value-weighted return per bucket over the period.
    bucket_value: dict[str, float] = {b: 0.0 for b in BUCKET_TARGETS}
    bucket_ret_accum: dict[str, float] = {b: 0.0 for b in BUCKET_TARGETS}
    for ticker, qty in holdings.items():
        closes = get_closes(ticker)
        if closes.empty:
            continue
        meta = get_position(ticker)
        bucket = meta.bucket if (meta and meta.bucket in BUCKET_TARGETS) else "single_stocks"
        value = qty * float(closes.iloc[-1])
        pr = _period_return(ticker, period)
        if pr is None:
            continue
        bucket_value[bucket] += value
        bucket_ret_accum[bucket] += value * pr

    total_value = sum(bucket_value.values())
    if total_value <= 0:
        return {"available": False, "reason": "no priced holdings"}

    portfolio_weights = {b: v / total_value for b, v in bucket_value.items()}
    portfolio_segment_returns = {
        b: (bucket_ret_accum[b] / bucket_value[b] if bucket_value[b] > 0 else 0.0)
        for b in BUCKET_TARGETS
    }
    benchmark_segment_returns = {
        b: (_period_return(_BUCKET_BENCHMARK[b], period) or 0.0) for b in BUCKET_TARGETS
    }

    result = brinson_attribution(
        portfolio_weights,
        BUCKET_TARGETS,
        portfolio_segment_returns,
        benchmark_segment_returns,
    )
    # Label segments for the UI.
    result["period"] = period
    result["available"] = True
    result["labels"] = {b: BUCKET_LABELS.get(b, b) for b in BUCKET_TARGETS}
    return result
