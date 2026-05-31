"""Kraken account balance and ticker prices.

Private balance needs read-only API credentials in ``.env``; public ticker
prices work without keys. All helpers degrade quietly (empty dict / None) when
credentials are missing, ``krakenex`` is unavailable, or a request fails.
"""
from __future__ import annotations

import os

from core.config import get_logger

logger = get_logger(__name__)

_api = None


def is_configured() -> bool:
    """True when private API credentials are present."""
    return bool(os.getenv("KRAKEN_API_KEY") and os.getenv("KRAKEN_API_SECRET"))


def _client():
    """Return an authenticated krakenex client, or None if unavailable."""
    global _api
    if _api is not None:
        return _api
    key = os.getenv("KRAKEN_API_KEY")
    secret = os.getenv("KRAKEN_API_SECRET")
    if not (key and secret):
        return None
    try:
        import krakenex

        _api = krakenex.API(key=key, secret=secret)
        return _api
    except Exception as e:  # noqa: BLE001
        logger.warning("kraken client init failed: %s", e)
        return None


def balance() -> dict[str, float]:
    """Return ``{asset: amount}``. Empty dict on failure."""
    api = _client()
    if not api:
        return {}
    try:
        r = api.query_private("Balance")
        if r.get("error"):
            logger.warning("kraken Balance error: %s", r["error"])
            return {}
        return {k: float(v) for k, v in r.get("result", {}).items()}
    except Exception as e:  # noqa: BLE001
        logger.warning("kraken balance failed: %s", e)
        return {}


def ticker_price(pair: str) -> float | None:
    """Return the last trade price for a public pair, e.g. ``'SOLEUR'``."""
    api = _client()
    if api is None:
        try:
            import krakenex

            api = krakenex.API()
        except Exception as e:  # noqa: BLE001
            logger.warning("kraken public client init failed: %s", e)
            return None
    try:
        r = api.query_public("Ticker", {"pair": pair})
        result = r.get("result", {})
        for v in result.values():
            return float(v["c"][0])  # last trade close
    except Exception as e:  # noqa: BLE001
        logger.warning("kraken ticker_price failed for %s: %s", pair, e)
        return None
    return None
