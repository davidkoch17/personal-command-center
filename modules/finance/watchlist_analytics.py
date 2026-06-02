"""Watchlist analytics (Phase 15d, Category I).

Scores every name in the vault ``Watchlist.md`` universe on the *same* metrics
used for held positions (Sharpe, vol, beta, drawdown, momentum), and models the
marginal effect of adding a watchlist name to the current portfolio. The point
of the "everything connects" layer: a candidate is judged on the identical
yardstick as something already owned.
"""
from __future__ import annotations

import re

import pandas as pd

from core import vault
from core.config import VAULT_PATH, get_logger

logger = get_logger(__name__)

WATCHLIST_FILE = VAULT_PATH / "4_Areas" / "Investing" / "Watchlist.md"

# Benchmark for beta (kept here so the API + frontend agree on the reference).
BETA_BENCHMARK = "^GSPC"
_MIN_DAYS = 60  # need at least ~3 months of data before a metric is meaningful


def watchlist_universe() -> list[str]:
    """Read Watchlist.md and return all unique tickers (parenthesised symbols)."""
    text = vault.read_md(WATCHLIST_FILE)
    if not text:
        return []
    # Parse out tickers in parens like (NKE), (^GSPC), (BTC-USD), (EURUSD=X).
    tickers = re.findall(r"\(([A-Z0-9.\-^]+(?:=[A-Z]+)?)\)", text)
    # Preserve first-seen order while de-duping.
    seen: dict[str, None] = {}
    for t in tickers:
        seen.setdefault(t, None)
    return list(seen.keys())


def watchlist_metrics() -> list[dict]:
    """For each watchlist ticker, compute Sharpe, vol, beta, momentum, drawdown."""
    from modules.finance.risk import sharpe, volatility, beta_vs, max_drawdown
    from modules.finance.price_history import get_returns

    out: list[dict] = []
    for t in watchlist_universe():
        try:
            r = get_returns(t)
            if len(r) < _MIN_DAYS:
                continue  # need at least 60 days of data
            vol_series = volatility(r, window_days=90).dropna()
            dd = max_drawdown(r)
            out.append({
                "ticker": t,
                "sharpe": sharpe(r),
                "volatility": float(vol_series.iloc[-1]) if not vol_series.empty else None,
                "beta": beta_vs(r, BETA_BENCHMARK),
                "max_drawdown": dd["magnitude"],
                "momentum_3m": float((1 + r.tail(63)).prod() - 1),    # ~3 months
                "momentum_12m": float((1 + r.tail(252)).prod() - 1),  # ~12 months
            })
        except Exception as exc:  # noqa: BLE001 — keep a bad ticker from killing the table
            logger.warning("watchlist metric failed for %s: %s", t, exc)
            out.append({"ticker": t, "error": str(exc)})
    return out


def add_to_portfolio_simulation(new_ticker: str, weight: float) -> dict:
    """Model the marginal effect of adding ``new_ticker`` at ``weight``.

    Approximation: ``new = (1 - weight) * existing + weight * candidate`` on the
    aligned daily-return series. Returns the before/after Sharpe, vol, beta and
    the deltas so the UI can show "what changes if I add this".
    """
    from modules.finance.performance import portfolio_returns
    from modules.finance.price_history import get_returns
    from modules.finance.risk import sharpe, annualized_vol, beta_vs

    existing = portfolio_returns()
    candidate = get_returns(new_ticker)
    if existing.empty or candidate.empty:
        return {"new_ticker": new_ticker, "weight": weight, "available": False,
                "reason": "no return series for portfolio and/or candidate"}

    aligned = pd.concat([existing, candidate], axis=1).dropna()
    aligned.columns = ["existing", "candidate"]
    if aligned.empty:
        return {"new_ticker": new_ticker, "weight": weight, "available": False,
                "reason": "no overlapping history"}

    w = max(0.0, min(1.0, float(weight)))
    blended = (1 - w) * aligned["existing"] + w * aligned["candidate"]

    before = {
        "sharpe": sharpe(aligned["existing"]),
        "volatility": annualized_vol(aligned["existing"]),
        "beta": beta_vs(aligned["existing"], BETA_BENCHMARK),
    }
    after = {
        "sharpe": sharpe(blended),
        "volatility": annualized_vol(blended),
        "beta": beta_vs(blended, BETA_BENCHMARK),
    }

    def _delta(key: str) -> float | None:
        a, b = after.get(key), before.get(key)
        return None if (a is None or b is None) else round(a - b, 4)

    return {
        "new_ticker": new_ticker,
        "weight": w,
        "available": True,
        "before": before,
        "after": after,
        "modeled_metrics": {
            "delta_sharpe": _delta("sharpe"),
            "delta_volatility": _delta("volatility"),
            "delta_beta": _delta("beta"),
            "correlation_to_portfolio": round(float(aligned["existing"].corr(aligned["candidate"])), 4),
        },
    }
