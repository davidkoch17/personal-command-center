"""Capital allocation planner (Phase 15d, Category J — Section 3.2).

Bridges the Money workspace (cash balance) to the Portfolio (bucket targets):
given deployable cash, suggest which underweight bucket to top up to move the
allocation toward the Section 0 four-bucket targets. The "you have €X cash;
bucket Y is underweight Z% — deploy €N to Y" view.
"""
from __future__ import annotations

from core.config import BUCKET_LABELS, get_logger
from modules.finance import decision_support as ds

logger = get_logger(__name__)


def suggest_deployment(cash: float | None = None) -> dict:
    """Suggest how to deploy ``cash`` across underweight buckets.

    If ``cash`` is None, reads the latest cash balance from the Money tracker.
    Deployment is proportional to each bucket's *post-deployment* target shortfall
    so that adding the cash moves every bucket toward its target weight.
    """
    if cash is None:
        from modules.finance.money import current_cash_balance
        cash = current_cash_balance()

    positions, prices = ds.current_positions_and_prices()
    pv = ds.portfolio_value(positions, prices)
    allocations = ds.bucket_allocations(positions, prices)

    cash = float(cash or 0.0)
    new_total = pv + cash

    suggestions: list[dict] = []
    # Shortfall = target share of the *new* total minus what's already invested.
    shortfalls = {
        b: max(0.0, alloc["target"] * new_total - alloc["value"])
        for b, alloc in allocations.items()
    }
    total_shortfall = sum(shortfalls.values())

    for bucket, alloc in allocations.items():
        shortfall = shortfalls[bucket]
        deploy = (shortfall / total_shortfall) * cash if (total_shortfall > 0 and cash > 0) else 0.0
        if deploy <= 0 and alloc["drift"] >= 0:
            continue
        suggestions.append({
            "bucket": bucket,
            "label": BUCKET_LABELS.get(bucket, bucket),
            "current_weight": alloc["weight"],
            "target_weight": alloc["target"],
            "drift_pct": alloc["drift"] * 100,
            "current_value": alloc["value"],
            "suggested_deploy_eur": round(deploy, 2),
            "rationale": (
                f"{BUCKET_LABELS.get(bucket, bucket)} at {alloc['weight'] * 100:.1f}% "
                f"vs target {alloc['target'] * 100:.0f}% — deploy €{deploy:,.0f}"
            ),
        })

    suggestions.sort(key=lambda s: s["suggested_deploy_eur"], reverse=True)
    return {
        "cash_deployable": cash,
        "portfolio_value": pv,
        "new_total": new_total,
        "suggestions": suggestions,
    }
