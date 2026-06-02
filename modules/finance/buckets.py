"""Four-bucket allocation tracking (Investment_Philosophy.md § 0, LOCKED).

Maps current holdings to their bucket, values them at the latest cached price,
and compares actual vs target allocation with drift bands + trigger alerts.

All positions are valued in their yfinance-native currency (USD for the current
ADR/crypto holdings), which cancels out when computing weights, so the bucket
percentages are basis-consistent even before FX normalization (a later phase).
"""
from __future__ import annotations

from core.config import (
    BUCKET_DRIFT_OK,
    BUCKET_DRIFT_WARN,
    BUCKET_LABELS,
    BUCKET_TARGETS,
    get_logger,
)
from modules.finance.positions import current_holdings, get_position
from modules.finance.price_history import latest_price

logger = get_logger(__name__)


def _drift_status(drift_abs: float) -> str:
    """Green within ±2pp, amber within ±5pp, red beyond."""
    if drift_abs <= BUCKET_DRIFT_OK:
        return "ok"
    if drift_abs <= BUCKET_DRIFT_WARN:
        return "warn"
    return "alert"


def bucket_allocation() -> dict:
    """Current bucket allocation vs target, with drift + trigger alerts.

    Holdings whose ticker has no position metadata fall into ``unassigned`` (kept
    out of the bucket weights but surfaced so nothing is silently dropped).
    """
    holdings = current_holdings()
    bucket_values: dict[str, float] = {b: 0.0 for b in BUCKET_TARGETS}
    unassigned: dict[str, float] = {}

    for ticker, qty in holdings.items():
        price = latest_price(ticker) or 0.0
        value = qty * price
        pos = get_position(ticker)
        if pos and pos.bucket in bucket_values:
            bucket_values[pos.bucket] += value
        else:
            unassigned[ticker] = value

    total = sum(bucket_values.values())
    buckets = []
    for key, target in BUCKET_TARGETS.items():
        value = bucket_values[key]
        current = value / total if total > 0 else 0.0
        drift = current - target
        buckets.append({
            "bucket": key,
            "label": BUCKET_LABELS[key],
            "value": round(value, 2),
            "current_weight": round(current, 4),
            "target_weight": target,
            "drift": round(drift, 4),
            "status": _drift_status(abs(drift)),
        })

    # Trigger alerts from the philosophy doc.
    alerts: list[dict] = []
    crypto_w = next((b["current_weight"] for b in buckets if b["bucket"] == "crypto"), 0.0)
    etf_w = next((b["current_weight"] for b in buckets if b["bucket"] == "etf_foundation"), 0.0)
    if crypto_w > 0.30:
        alerts.append({"severity": "trim", "bucket": "crypto",
                       "message": f"Crypto at {crypto_w:.0%} (> 30%) — trim sleeve back toward 24%; proceeds to ETF foundation."})
    if etf_w < 0.45:
        alerts.append({"severity": "rebalance", "bucket": "etf_foundation",
                       "message": f"ETF foundation at {etf_w:.0%} (< 45%) — add to VWCE / CSPX / STOXX to rebuild the core."})

    return {
        "total_value": round(total, 2),
        "buckets": buckets,
        "unassigned": [{"ticker": t, "value": round(v, 2)} for t, v in unassigned.items()],
        "alerts": alerts,
    }
