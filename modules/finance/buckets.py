"""Four-bucket allocation tracking (Investment_Philosophy.md § 0, LOCKED).

Maps current holdings to their bucket, values them at the latest cached price,
and compares actual vs target allocation with drift bands + trigger alerts.

All positions are valued in their yfinance-native currency (USD for the current
ADR/crypto holdings), which cancels out when computing weights, so the bucket
percentages are basis-consistent even before FX normalization (a later phase).

Bucket resolution (Chunk 2.5 — hybrid assignment) is read-time, not persisted:
:func:`resolve_bucket` checks a per-position override in ``positions.json``
first, falls back to the ``config/ticker_buckets.yaml`` seed map, and finally
"unassigned". Nothing writes the map's answer back into a position record —
that would make a stale map lookup indistinguishable from a real user
override and break "clear override" (it needs to know whether to revert to
*computed-fresh-from-the-map* or to nothing). Recomputing on every call is
trivially idempotent and always reflects the current map/override state.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from core.config import (
    BUCKET_DRIFT_OK,
    BUCKET_DRIFT_WARN,
    BUCKET_LABELS,
    BUCKET_TARGETS,
    TICKER_BUCKETS_FILE,
    get_logger,
)
from modules.finance.positions import current_holdings, get_position
from modules.finance.price_history import latest_price

logger = get_logger(__name__)

# mtime-cached ticker->bucket map — no existing config reader in this repo
# caches (excel_import.load_config() re-parses every call), so this is a
# fresh, self-contained pattern rather than a mirrored one.
_map_cache: Optional[dict[str, str]] = None
_map_mtime: Optional[float] = None


def _load_ticker_bucket_map(path: Path = TICKER_BUCKETS_FILE) -> dict[str, str]:
    """Flat TICKER->bucket dict from ``config/ticker_buckets.yaml``.

    Reloads only when the file's mtime changes; returns {} if the file is
    missing (never raises — an absent/empty map just means every ticker falls
    through to "unassigned").
    """
    global _map_cache, _map_mtime
    if not path.exists():
        return {}
    mtime = path.stat().st_mtime
    if _map_cache is not None and _map_mtime == mtime:
        return _map_cache
    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except (yaml.YAMLError, OSError) as exc:  # noqa: BLE001
        logger.warning("ticker_buckets.yaml unreadable: %s", exc)
        return _map_cache or {}
    _map_cache = {str(k).upper(): v for k, v in raw.items() if isinstance(v, str)}
    _map_mtime = mtime
    return _map_cache


def infer_bucket(ticker: str) -> Optional[str]:
    """Bucket inferred from the ticker->bucket seed map (None if not listed)."""
    return _load_ticker_bucket_map().get(ticker.upper())


def resolve_bucket_with_source(ticker: str) -> tuple[str, str]:
    """``(bucket, source)`` — override (positions.json) wins over the seed map,
    which wins over "unassigned". ``source`` is one of "override" / "map" /
    "unassigned", so callers (the Holdings-tab bucket cell) can show the
    auto-vs-custom indicator without a second lookup."""
    pos = get_position(ticker)
    if pos is not None and pos.bucket:
        return pos.bucket, "override"
    mapped = infer_bucket(ticker)
    if mapped:
        return mapped, "map"
    return "unassigned", "unassigned"


def resolve_bucket(ticker: str) -> str:
    """Just the resolved bucket string (see :func:`resolve_bucket_with_source`)."""
    return resolve_bucket_with_source(ticker)[0]


def _drift_status(drift_abs: float) -> str:
    """Green within ±2pp, amber within ±5pp, red beyond."""
    if drift_abs <= BUCKET_DRIFT_OK:
        return "ok"
    if drift_abs <= BUCKET_DRIFT_WARN:
        return "warn"
    return "alert"


def bucket_allocation() -> dict:
    """Current bucket allocation vs target, with drift + trigger alerts.

    Holdings that resolve to "unassigned" (no override, not in the seed map)
    are kept out of the bucket weights but surfaced so nothing is silently
    dropped.
    """
    holdings = current_holdings()
    bucket_values: dict[str, float] = {b: 0.0 for b in BUCKET_TARGETS}
    unassigned: dict[str, float] = {}

    for ticker, qty in holdings.items():
        price = latest_price(ticker) or 0.0
        value = qty * price
        bucket = resolve_bucket(ticker)
        if bucket in bucket_values:
            bucket_values[bucket] += value
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
