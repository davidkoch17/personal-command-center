"""Decision support — sizing, rebalancing, tax-loss harvesting, alerts.

Phase 15c, Category F. The actionable layer: it turns the 15a/15b analytics into
specific suggestions David can act on, enforcing the rules in
``Investment_Philosophy.md`` (Sections 0, 17, 18) as literal gates.

The pure-calculation functions (``suggested_position_size``,
``bucket_allocations``, ``rebalance_recommendations``, ``harvest_candidates``,
``concentration_alerts``) take plain ``positions`` (list of dicts with
``ticker`` / ``quantity`` / ``bucket`` / ``type``) and a ``prices`` dict so they
stay easy to unit-test. :func:`current_positions_and_prices` assembles those from
the live holdings + price cache, and the ``backend/api/finance/decisions.py``
endpoints are thin wrappers over both.

NOTE on the conviction → size gates: Investment Philosophy Section 7.1 (the
5-Layer Research Framework + 6-Point Conviction Scorecard) was not yet locked
when this was built, so ``CONVICTION_TO_SIZE`` below encodes David's v3 working
defaults. When Section 7.1 is finalized, swap the mapping here — it is the single
source of truth the rest of the layer reads.
"""
from __future__ import annotations

from datetime import date

from modules.finance.positions import (
    cost_basis,
    current_holdings,
    get_position,
    transactions_for,
)
from modules.finance.price_history import latest_price


# ============================================================
# Position sizing (per Investment_Philosophy.md Section 17)
# ============================================================

# v3 working default until Section 7.1 is locked — see module docstring.
CONVICTION_TO_SIZE = {
    6: 0.05,    # 5% max
    5: 0.04,
    4: 0.025,
    3: 0.015,   # 1.5% minimum entry
    2: 0.0,     # No entry
    1: 0.0,
    0: 0.0,
}


def suggested_position_size(conviction_score: int, portfolio_value: float) -> dict:
    """Map conviction score to position size + EUR amount."""
    weight = CONVICTION_TO_SIZE.get(conviction_score, 0)
    return {
        "conviction_score": conviction_score,
        "weight_pct": weight * 100,
        "eur_amount": weight * portfolio_value,
        "can_enter": weight > 0,
        "rationale": f"Conviction {conviction_score}/6 maps to {weight*100:.1f}% per Investment Philosophy Section 17",
    }


# ============================================================
# Rebalance suggestor (per Section 18 cross-bucket rebalancing)
# ============================================================

BUCKET_TARGETS = {
    "etf_foundation": 0.49,
    "single_stocks": 0.21,
    "crypto": 0.24,
    "wild_cards": 0.06,
}
BUCKET_DRIFT_TOLERANCE = 0.04  # ±4 percentage points before triggering rebalance


def bucket_allocations(positions: list, prices: dict) -> dict:
    """Compute current allocation per bucket."""
    bucket_values = {b: 0.0 for b in BUCKET_TARGETS}
    for p in positions:
        bucket = p.get("bucket", "single_stocks")
        qty = p.get("quantity", 0)
        price = prices.get(p["ticker"], 0)
        if bucket not in bucket_values:
            bucket = "single_stocks"
        bucket_values[bucket] += qty * price
    total = sum(bucket_values.values())
    if total == 0:
        return {b: {"value": 0, "weight": 0, "target": t, "drift": -t} for b, t in BUCKET_TARGETS.items()}
    return {
        b: {
            "value": bucket_values[b],
            "weight": bucket_values[b] / total,
            "target": BUCKET_TARGETS[b],
            "drift": bucket_values[b] / total - BUCKET_TARGETS[b],
        }
        for b in BUCKET_TARGETS
    }


def rebalance_recommendations(allocations: dict, portfolio_value: float) -> list[dict]:
    """Generate rebalancing trade suggestions to bring allocations within tolerance."""
    recs = []
    for bucket, alloc in allocations.items():
        drift = alloc["drift"]
        if abs(drift) > BUCKET_DRIFT_TOLERANCE:
            target_value = alloc["target"] * portfolio_value
            current_value = alloc["value"]
            delta = target_value - current_value
            action = "buy" if delta > 0 else "sell"
            recs.append({
                "bucket": bucket,
                "action": action,
                "current_weight": alloc["weight"],
                "target_weight": alloc["target"],
                "drift_pct": drift * 100,
                "delta_eur": delta,
                "priority": "high" if abs(drift) > 0.06 else "medium",
                "rationale": f"{bucket} at {alloc['weight']*100:.1f}% vs target {alloc['target']*100:.0f}% — {'trim' if delta < 0 else 'add'} €{abs(delta):,.0f}",
            })
    # Special rule: crypto > 30% → forced trim to 24% with proceeds to ETF (per Section 0.3)
    if allocations.get("crypto", {}).get("weight", 0) > 0.30:
        recs.insert(0, {
            "bucket": "crypto",
            "action": "trim_to_target",
            "rationale": "Crypto sleeve exceeded 30% trigger — trim to 24%, proceeds go to ETF Foundation (never recycled into crypto)",
            "priority": "high",
            "delta_eur": (allocations["crypto"]["weight"] - 0.24) * portfolio_value,
        })
    return recs


# ============================================================
# Tax-loss harvesting (German Spekulationsfrist)
# ============================================================

def harvest_candidates(positions: list, prices: dict, today: date | None = None) -> list[dict]:
    """Identify positions at a loss that could be sold for tax purposes.

    German rules:
    - Equities: gains taxed via Abgeltungsteuer (~26.4%); losses offset gains
    - Crypto: holding > 12 months = tax-free (Spekulationsfrist). Don't harvest crypto < 12 months unless intentional.
    - Sparerpauschbetrag: €1,000/year tax-free for equity gains
    """
    today = today or date.today()
    candidates = []
    for p in positions:
        ticker = p["ticker"]
        qty = p["quantity"]
        avg_cost, _ = cost_basis(ticker)
        current_price = prices.get(ticker, 0)
        if not avg_cost or not current_price:
            continue
        unrealized_pnl = (current_price - avg_cost) * qty
        unrealized_pnl_pct = (current_price - avg_cost) / avg_cost

        if unrealized_pnl < 0:
            # Check holding period. ``transactions_for`` returns Transaction
            # objects (pydantic), so use attribute access, not subscripting.
            txs = transactions_for(ticker)
            earliest_buy = min((t.date for t in txs if t.action == "buy"), default=today)
            holding_days = (today - earliest_buy).days

            crypto = p.get("type") == "crypto"

            # For crypto: only harvest if < 12 months (otherwise gain would be tax-free anyway)
            # For equities: always candidate when at loss
            should_consider = True
            if crypto and holding_days < 365:
                # Loss can offset other crypto gains, but holding to 365d for tax-free gain might be better strategy
                should_consider = True
            elif crypto and holding_days >= 365:
                # If sold at gain, would be tax-free — losses here don't help tax-wise
                should_consider = False

            if should_consider:
                candidates.append({
                    "ticker": ticker,
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_pnl_pct": unrealized_pnl_pct * 100,
                    "holding_days": holding_days,
                    "type": p.get("type"),
                    "tax_savings_estimate": abs(unrealized_pnl) * 0.264 if not crypto else abs(unrealized_pnl) * 0.42,  # rough
                    "warning": "Crypto loss — but consider holding to 12 months for tax-free gain potential" if crypto else None,
                })
    return sorted(candidates, key=lambda x: x["unrealized_pnl"])


# ============================================================
# Concentration + drift alerts
# ============================================================

def concentration_alerts(positions: list, prices: dict) -> list[dict]:
    """Alert if any position exceeds Section 0.2 max position (5% in Single Stocks)
    or if bucket cap exceeded."""
    alerts = []
    total = sum(p["quantity"] * prices.get(p["ticker"], 0) for p in positions)
    if total == 0:
        return []

    # Per-position check
    for p in positions:
        value = p["quantity"] * prices.get(p["ticker"], 0)
        weight = value / total
        bucket = p.get("bucket", "single_stocks")

        if bucket == "single_stocks":
            if weight > 0.07:  # 7% drift trigger per Section 0.2
                alerts.append({
                    "type": "drift_trigger",
                    "ticker": p["ticker"],
                    "weight": weight,
                    "rationale": f"{p['ticker']} at {weight*100:.1f}% — Section 0.2 says trim to 5% when above 7%",
                    "severity": "high",
                })
            elif weight > 0.05:
                alerts.append({
                    "type": "approaching_max",
                    "ticker": p["ticker"],
                    "weight": weight,
                    "rationale": f"{p['ticker']} at {weight*100:.1f}% — max single position is 5%",
                    "severity": "medium",
                })
        elif bucket == "crypto":
            if weight > 0.08:  # Per Section 0.3, max 8% per crypto position
                alerts.append({
                    "type": "crypto_position_cap",
                    "ticker": p["ticker"],
                    "weight": weight,
                    "rationale": f"{p['ticker']} at {weight*100:.1f}% — Section 0.3 caps each crypto at 8%",
                    "severity": "high",
                })
        elif bucket == "wild_cards":
            if weight > 0.02:
                alerts.append({
                    "type": "wild_card_position_cap",
                    "ticker": p["ticker"],
                    "weight": weight,
                    "rationale": f"{p['ticker']} at {weight*100:.1f}% — Section 0.4 caps each wild card at 2%",
                    "severity": "high",
                })

    return alerts


# ============================================================
# Hypothesis-conviction-weighted views
# ============================================================

def conviction_weighted_view() -> dict:
    """Read hypothesis tracker, weight portfolio analysis by conviction levels."""
    from modules.finance.optimization import hypotheses_as_views
    views = hypotheses_as_views()
    # Calculate aggregate conviction-weighted expected return
    total_confidence = sum(v["confidence"] for v in views)
    if total_confidence == 0:
        return {"views": [], "aggregate_expected_return": None, "n_views": 0}
    weighted_return = sum(v["expected_return"] * v["confidence"] for v in views) / total_confidence
    return {
        "views": views,
        "aggregate_expected_return": weighted_return,
        "n_views": len(views),
    }


# ============================================================
# Live-state assembly (used by the API layer)
# ============================================================

def current_positions_and_prices() -> tuple[list[dict], dict[str, float]]:
    """Assemble the pure-function inputs from live holdings + the price cache.

    ``positions`` is a list of ``{ticker, quantity, bucket, type}`` dicts; holdings
    with no position metadata fall back to the ``single_stocks`` bucket so they're
    never silently dropped from the checks.
    """
    holdings = current_holdings()
    positions: list[dict] = []
    prices: dict[str, float] = {}
    for ticker, qty in holdings.items():
        meta = get_position(ticker)
        prices[ticker] = latest_price(ticker) or 0.0
        positions.append({
            "ticker": ticker,
            "quantity": qty,
            "bucket": meta.bucket if meta else "single_stocks",
            "type": meta.type if meta else None,
        })
    return positions, prices


def portfolio_value(positions: list, prices: dict) -> float:
    """Total market value of the supplied positions at the supplied prices."""
    return sum(p["quantity"] * prices.get(p["ticker"], 0) for p in positions)


def decision_summary() -> dict:
    """Bundle counts + headline figures for the Home 'decision alerts' panel."""
    positions, prices = current_positions_and_prices()
    pv = portfolio_value(positions, prices)
    allocations = bucket_allocations(positions, prices)
    rebal = rebalance_recommendations(allocations, pv)
    harvest = harvest_candidates(positions, prices)
    alerts = concentration_alerts(positions, prices)
    return {
        "portfolio_value": pv,
        "rebalance_count": len(rebal),
        "rebalance_high": sum(1 for r in rebal if r.get("priority") == "high"),
        "concentration_count": len(alerts),
        "concentration_high": sum(1 for a in alerts if a.get("severity") == "high"),
        "harvest_count": len(harvest),
        "harvest_savings": sum(c["tax_savings_estimate"] for c in harvest),
    }
