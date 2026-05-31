"""Whoop API client. OAuth2 with refresh tokens.

All fetch helpers degrade to ``None`` when credentials are missing, the token
refresh fails, or ``httpx`` is unavailable. :func:`summary` flattens the raw
API payloads into the handful of numbers the dashboard renders.
"""
from __future__ import annotations

import os

from core.config import get_logger

logger = get_logger(__name__)

API_BASE = "https://api.prod.whoop.com/developer/v1"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"


def is_configured() -> bool:
    """True when the OAuth client + refresh token are all present."""
    return all(
        os.getenv(k)
        for k in ("WHOOP_CLIENT_ID", "WHOOP_CLIENT_SECRET", "WHOOP_REFRESH_TOKEN")
    )


def _refresh_access_token() -> str:
    import httpx

    refresh = os.getenv("WHOOP_REFRESH_TOKEN")
    client_id = os.getenv("WHOOP_CLIENT_ID")
    client_secret = os.getenv("WHOOP_CLIENT_SECRET")
    if not all([refresh, client_id, client_secret]):
        raise RuntimeError("Whoop credentials missing in .env")
    r = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "offline",
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _get(path: str, params: dict | None = None) -> dict:
    import httpx

    token = _refresh_access_token()
    r = httpx.get(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def latest_recovery() -> dict | None:
    try:
        data = _get("/recovery", params={"limit": 1})
        records = data.get("records", [])
        return records[0] if records else None
    except Exception as e:  # noqa: BLE001
        logger.warning("whoop latest_recovery failed: %s", e)
        return None


def latest_sleep() -> dict | None:
    try:
        data = _get("/activity/sleep", params={"limit": 1})
        records = data.get("records", [])
        return records[0] if records else None
    except Exception as e:  # noqa: BLE001
        logger.warning("whoop latest_sleep failed: %s", e)
        return None


def latest_cycle() -> dict | None:
    try:
        data = _get("/cycle", params={"limit": 1})
        records = data.get("records", [])
        return records[0] if records else None
    except Exception as e:  # noqa: BLE001
        logger.warning("whoop latest_cycle failed: %s", e)
        return None


def summary() -> dict:
    """Flatten Whoop payloads into dashboard metrics.

    Returns ``{configured, recovery, hrv, sleep_hours, strain}`` where each
    metric is a float or None. Only makes network calls when configured.
    """
    out = {
        "configured": is_configured(),
        "recovery": None,
        "hrv": None,
        "sleep_hours": None,
        "strain": None,
    }
    if not out["configured"]:
        return out

    rec = latest_recovery()
    if rec and isinstance(rec.get("score"), dict):
        out["recovery"] = rec["score"].get("recovery_score")
        out["hrv"] = rec["score"].get("hrv_rmssd_milli")

    sleep = latest_sleep()
    if sleep and isinstance(sleep.get("score"), dict):
        stage = sleep["score"].get("stage_summary", {}) or {}
        in_bed_milli = stage.get("total_in_bed_time_milli")
        if in_bed_milli:
            out["sleep_hours"] = round(in_bed_milli / 3_600_000, 1)

    cycle = latest_cycle()
    if cycle and isinstance(cycle.get("score"), dict):
        out["strain"] = cycle["score"].get("strain")

    return out
