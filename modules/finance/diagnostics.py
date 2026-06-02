"""Finance data-source health + cache freshness (Phase 15e, Section 4).

Powers the Settings "data sources" panel: is each upstream reachable, and how
fresh is each on-disk cache? Checks are cheap (filesystem stats + one tiny
network probe) and never raise — each returns a ``{name, status, detail}`` row
matching the integration-diagnostics shape the Settings UI already renders.
"""
from __future__ import annotations

from datetime import date, datetime

from core.config import (
    DATA_DIR,
    POSITIONS_FILE,
    PRICE_CACHE_DIR,
    TRANSACTIONS_FILE,
)
from modules.finance.factors import FF_CACHE_DIR

# status values mirror the integrations diagnostics: ok / error / not_configured.


def _newest_mtime(directory) -> datetime | None:
    """Most-recent modification time across files in a directory (None if empty)."""
    if not directory.exists():
        return None
    mtimes = [f.stat().st_mtime for f in directory.glob("*") if f.is_file()]
    if not mtimes:
        return None
    return datetime.fromtimestamp(max(mtimes))


def _age_str(dt: datetime | None) -> str:
    if dt is None:
        return "never"
    days = (datetime.now() - dt).days
    if days == 0:
        return "today"
    return f"{days}d ago"


def _check_price_cache() -> dict:
    newest = _newest_mtime(PRICE_CACHE_DIR)
    n = len(list(PRICE_CACHE_DIR.glob("*.parquet"))) if PRICE_CACHE_DIR.exists() else 0
    if n == 0:
        return {"name": "price cache (yfinance)", "status": "not_configured",
                "detail": "no cached tickers yet"}
    fresh = newest is not None and (datetime.now() - newest).days < 1
    return {
        "name": "price cache (yfinance)",
        "status": "ok" if fresh else "error",
        "detail": f"{n} tickers · updated {_age_str(newest)}",
    }


def _check_ff_cache() -> dict:
    newest = _newest_mtime(FF_CACHE_DIR)
    n = len(list(FF_CACHE_DIR.glob("*.parquet"))) if FF_CACHE_DIR.exists() else 0
    if n == 0:
        return {"name": "fama-french factor cache", "status": "not_configured",
                "detail": "not fetched yet (refresh monthly)"}
    stale = newest is not None and (datetime.now() - newest).days > 30
    return {
        "name": "fama-french factor cache",
        "status": "error" if stale else "ok",
        "detail": f"{n} datasets · updated {_age_str(newest)}",
    }


def _check_store(label: str, path) -> dict:
    if not path.exists():
        return {"name": label, "status": "not_configured", "detail": "no file yet"}
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return {"name": label, "status": "ok", "detail": f"updated {_age_str(mtime)}"}


def _check_yfinance_live() -> dict:
    """One tiny live probe so we know yfinance/network is actually reachable."""
    try:
        from modules.finance.price_history import latest_price

        px = latest_price("SPY")
        if px:
            return {"name": "yfinance reachable", "status": "ok", "detail": f"SPY @ {px:.2f}"}
        return {"name": "yfinance reachable", "status": "error", "detail": "no quote returned"}
    except Exception as exc:  # noqa: BLE001
        return {"name": "yfinance reachable", "status": "error", "detail": str(exc)[:80]}


def _check_fx() -> dict:
    try:
        from modules.finance.currency import get_fx_rate

        rate = get_fx_rate("EUR", "USD")
        if rate:
            return {"name": "fx rates (EUR/USD)", "status": "ok", "detail": f"{rate:.4f}"}
        return {"name": "fx rates (EUR/USD)", "status": "error", "detail": "no rate"}
    except Exception as exc:  # noqa: BLE001
        return {"name": "fx rates (EUR/USD)", "status": "error", "detail": str(exc)[:80]}


def run_all(probe_network: bool = False) -> list[dict]:
    """All finance data-source checks. ``probe_network`` adds live yfinance/FX hits."""
    checks = [
        _check_store("positions store", POSITIONS_FILE),
        _check_store("transactions log", TRANSACTIONS_FILE),
        _check_price_cache(),
        _check_ff_cache(),
    ]
    if probe_network:
        checks.append(_check_yfinance_live())
        checks.append(_check_fx())
    return checks
