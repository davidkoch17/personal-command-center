"""Portfolio optimization — efficient frontier, Markowitz, Black-Litterman.

Phase 15b, Category D. Sits on top of the 15a price-history + positions layer and
wraps PyPortfolioOpt. Every optimizer takes a ticker list (defaults to current
holdings) and an optional constraints dict that encodes the Section 0 bucket
discipline (max/min single-position weight).

Black-Litterman folds David's `Hypothesis_Tracker.md` convictions in as views —
see :func:`hypotheses_as_views` for how the markdown is parsed.
"""
from __future__ import annotations

import re
from typing import Optional

import numpy as np
import pandas as pd

from core.config import DEFAULT_BENCHMARK, BENCHMARKS, get_logger
from modules.finance.price_history import get_returns
from modules.finance.positions import current_holdings, list_positions

logger = get_logger(__name__)

TRADING_DAYS = 252


def _resolve_tickers(tickers: Optional[list[str]]) -> list[str]:
    """Default to current holdings; de-dupe while preserving order."""
    src = tickers if tickers else list(current_holdings().keys())
    seen: dict[str, None] = {}
    for t in src:
        if t and t not in seen:
            seen[t] = None
    return list(seen.keys())


def get_returns_matrix(tickers: list[str], lookback_years: int = 5) -> pd.DataFrame:
    """Aligned daily-returns DataFrame for ``tickers`` over the lookback window."""
    rets = {}
    for t in tickers:
        r = get_returns(t)
        if not r.empty:
            rets[t] = r
        else:
            logger.warning("No returns for %s; excluded from optimization", t)
    if not rets:
        return pd.DataFrame()
    df = pd.DataFrame(rets).dropna()
    if lookback_years and not df.empty:
        cutoff = df.index.max() - pd.DateOffset(years=lookback_years)
        df = df[df.index >= cutoff]
    return df


def expected_returns_capm(
    tickers: list[str],
    market_ticker: str = "URTH",
    risk_free: float = 0.04,
) -> pd.Series:
    """CAPM-implied (equilibrium) annual expected returns per ticker."""
    rets = get_returns_matrix(tickers + [market_ticker])
    if rets.empty or market_ticker not in rets:
        return pd.Series(dtype="float64")
    market = rets[market_ticker]
    market_mean = market.mean() * TRADING_DAYS
    var = market.var()
    er = {}
    for t in tickers:
        if t not in rets:
            continue
        beta = rets[t].cov(market) / var if var else 0.0
        er[t] = float(risk_free + beta * (market_mean - risk_free))
    return pd.Series(er)


def expected_returns_mean(tickers: list[str], lookback_years: int = 5) -> pd.Series:
    """Historical mean returns, annualized (PyPortfolioOpt)."""
    from pypfopt import expected_returns

    df = get_returns_matrix(tickers, lookback_years)
    if df.empty:
        return pd.Series(dtype="float64")
    return expected_returns.mean_historical_return(df, frequency=TRADING_DAYS, returns_data=True)


def covariance_matrix(tickers: list[str], lookback_years: int = 5) -> pd.DataFrame:
    """Annualized sample covariance matrix (PyPortfolioOpt)."""
    from pypfopt import risk_models

    df = get_returns_matrix(tickers, lookback_years)
    if df.empty:
        return pd.DataFrame()
    return risk_models.sample_cov(df, frequency=TRADING_DAYS, returns_data=True)


def _perf_dict(perf: tuple) -> dict:
    """Normalize PyPortfolioOpt's (ret, vol, sharpe) tuple to a labelled dict."""
    return {
        "expected_return": float(perf[0]),
        "volatility": float(perf[1]),
        "sharpe": float(perf[2]),
    }


def efficient_frontier_points(tickers: list[str], n_points: int = 50) -> list[dict]:
    """Efficient frontier as (risk, return, weights) triplets."""
    from pypfopt import EfficientFrontier

    mu = expected_returns_mean(tickers)
    S = covariance_matrix(tickers)
    if mu.empty or S.empty:
        return []
    points: list[dict] = []
    target_returns = np.linspace(mu.min(), mu.max(), n_points)
    for target in target_returns:
        try:
            ef = EfficientFrontier(mu, S)
            ef.efficient_return(target_return=float(target))
            perf = ef.portfolio_performance()
            points.append({
                "target_return": float(target),
                "risk": float(perf[1]),
                "return": float(perf[0]),
                "sharpe": float(perf[2]),
                "weights": {k: round(float(v), 4) for k, v in ef.clean_weights().items()},
            })
        except Exception:  # noqa: BLE001 — infeasible targets are simply skipped
            continue
    return points


def min_variance_portfolio(tickers: list[str], constraints: dict | None = None) -> dict:
    from pypfopt import EfficientFrontier

    mu = expected_returns_mean(tickers)
    S = covariance_matrix(tickers)
    if mu.empty or S.empty:
        return {"weights": {}, "performance": None}
    ef = EfficientFrontier(mu, S)
    _apply_constraints(ef, constraints)
    ef.min_volatility()
    return {"weights": {k: round(float(v), 4) for k, v in ef.clean_weights().items()},
            "performance": _perf_dict(ef.portfolio_performance())}


def max_sharpe_portfolio(tickers: list[str], risk_free: float = 0.04, constraints: dict | None = None) -> dict:
    from pypfopt import EfficientFrontier

    mu = expected_returns_mean(tickers)
    S = covariance_matrix(tickers)
    if mu.empty or S.empty:
        return {"weights": {}, "performance": None}
    ef = EfficientFrontier(mu, S)
    _apply_constraints(ef, constraints)
    try:
        ef.max_sharpe(risk_free_rate=risk_free)
    except Exception as exc:  # noqa: BLE001 — e.g. all expected returns < rf
        logger.warning("max_sharpe failed (%s); falling back to min_volatility", exc)
        ef = EfficientFrontier(mu, S)
        _apply_constraints(ef, constraints)
        ef.min_volatility()
    return {"weights": {k: round(float(v), 4) for k, v in ef.clean_weights().items()},
            "performance": _perf_dict(ef.portfolio_performance())}


def risk_parity_weights(tickers: list[str]) -> dict:
    """Inverse-volatility (naive risk-parity) weights."""
    df = get_returns_matrix(tickers)
    if df.empty:
        return {}
    vols = df.std() * np.sqrt(TRADING_DAYS)
    inv_vol = 1 / vols
    weights = inv_vol / inv_vol.sum()
    return {k: round(float(v), 4) for k, v in weights.items()}


def _apply_constraints(ef, constraints: dict | None) -> None:
    """Apply Section 0 bucket constraints (max / min single-position weight)."""
    if not constraints:
        return
    if constraints.get("max_position") is not None:
        cap = float(constraints["max_position"])
        ef.add_constraint(lambda w: w <= cap)
    if constraints.get("min_position") is not None:
        floor = float(constraints["min_position"])
        ef.add_constraint(lambda w: w >= floor)


def black_litterman_with_hypotheses(
    tickers: list[str],
    market_caps: dict[str, float] | None = None,
    views: list[dict] | None = None,
    risk_aversion: float = 2.5,
) -> dict:
    """Black-Litterman: blend market (CAPM) equilibrium with David's views.

    ``views``: ``[{ticker, expected_return (annual decimal), confidence 0-1}, …]``.
    Confidence maps inversely to view uncertainty (omega). With no views, this
    degrades to the plain max-Sharpe portfolio. ``market_caps`` is accepted for
    API symmetry but unused in this CAPM-prior variant.
    """
    from pypfopt import BlackLittermanModel, EfficientFrontier

    mu_market = expected_returns_capm(tickers)
    S = covariance_matrix(tickers)
    if S.empty or mu_market.empty:
        return {"weights": {}, "performance": None, "views_used": []}

    used = [v for v in (views or []) if v.get("ticker") in tickers]
    if not used:
        result = max_sharpe_portfolio(tickers)
        result["posterior_returns"] = {k: round(float(v), 4) for k, v in mu_market.items()}
        result["market_equilibrium"] = {k: round(float(v), 4) for k, v in mu_market.items()}
        result["views_used"] = []
        return result

    P = np.zeros((len(used), len(tickers)))
    Q = np.zeros(len(used))
    omega_diag = []
    for i, view in enumerate(used):
        j = tickers.index(view["ticker"])
        P[i, j] = 1
        Q[i] = float(view["expected_return"])
        conf = float(view.get("confidence", 0.5))
        # Higher confidence -> lower omega (more weight on the view).
        omega_diag.append((1 - conf + 0.1) * S.values[j, j])
    Omega = np.diag(omega_diag)

    bl = BlackLittermanModel(S, pi=mu_market, P=P, Q=Q, omega=Omega, risk_aversion=risk_aversion)
    posterior_mu = bl.bl_returns()

    ef = EfficientFrontier(posterior_mu, S)
    try:
        ef.max_sharpe()
    except Exception as exc:  # noqa: BLE001
        logger.warning("BL max_sharpe failed (%s); using min_volatility", exc)
        ef = EfficientFrontier(posterior_mu, S)
        ef.min_volatility()
    return {
        "weights": {k: round(float(v), 4) for k, v in ef.clean_weights().items()},
        "performance": _perf_dict(ef.portfolio_performance()),
        "posterior_returns": {k: round(float(v), 4) for k, v in posterior_mu.items()},
        "market_equilibrium": {k: round(float(v), 4) for k, v in mu_market.items()},
        "views_used": used,
    }


# --- Hypothesis tracker integration -----------------------------------------

# Conviction (X/5) -> annual expected return when the tracker gives no explicit
# number. Anchored at a ~market-like 8% for a neutral 3/5 and tilted ±5pp per
# conviction step. These are transparent defaults, flagged ``derived`` so the UI
# can show them and David can override per-view.
_CONVICTION_RETURN = {1: -0.02, 2: 0.03, 3: 0.08, 4: 0.13, 5: 0.18}

# Map names that appear in hypothesis prose to held tickers.
_NAME_TICKER = {
    "alphabet": "GOOGL", "google": "GOOGL", "googl": "GOOGL",
    "alibaba": "BABA", "baba": "BABA",
    "byd": "BYDDY", "byddy": "BYDDY",
    "solana": "SOL", "sol": "SOL",
}


def _ticker_from_text(text: str) -> str | None:
    """Find a held/known ticker mentioned in a hypothesis header/body."""
    known = {p.ticker.upper() for p in list_positions()}
    upper = text.upper()
    for tk in known:
        if re.search(rf"\b{re.escape(tk)}\b", upper):
            return tk
    low = text.lower()
    for name, tk in _NAME_TICKER.items():
        if re.search(rf"\b{re.escape(name)}\b", low):
            return tk
    return None


def hypotheses_as_views() -> list[dict]:
    """Parse `Hypothesis_Tracker.md` into Black-Litterman views.

    Two formats are recognised:

    1. **Spec format** — sections headed ``## YYYY-MM-DD — TICKER`` with an
       explicit ``Conviction: X/5`` and ``Expected return: Y%`` in the body.
    2. **Actual tracker format** — ``**H1 — "…"**`` bullets carrying
       ``*Conviction:* **X/5**`` with the ticker named in the prose. The tracker
       rarely states an expected return, so one is derived from conviction (see
       ``_CONVICTION_RETURN``) and the view is flagged ``derived: True``.

    Each view: ``{ticker, expected_return, confidence, derived, label}``.
    """
    from core import vault
    from core.config import VAULT_PATH

    path = VAULT_PATH / "4_Areas" / "Investing" / "Hypothesis_Tracker.md"
    if not path.exists():
        return []
    text = vault.read_md(path)
    views: list[dict] = []
    seen_tickers: set[str] = set()

    # --- Format 1: ## YYYY-MM-DD — TICKER --------------------------------
    # ``[\s*]*`` after the colon absorbs any markdown emphasis (e.g. ``**3/5**``).
    for section in re.split(r"(?m)^## ", text)[1:]:
        first_line, _, body = section.partition("\n")
        m = re.match(r"\d{4}-\d{2}-\d{2}\s*[—-]\s*([A-Z0-9.\-]+)", first_line.strip())
        if not m:
            continue
        ticker = m.group(1)
        conv_m = re.search(r"Conviction:[\s*]*([12345])", body)
        ret_m = re.search(r"[Ee]xpected\s+return.*?([+\-]?\d+\.?\d*)\s*%", body)
        if conv_m and ret_m:
            views.append({
                "ticker": ticker,
                "expected_return": float(ret_m.group(1)) / 100.0,
                "confidence": int(conv_m.group(1)) / 5.0,
                "derived": False,
                "label": first_line.strip(),
            })
            seen_tickers.add(ticker)

    if views:
        return views

    # --- Format 2: **H# — "…"** bullets with *Conviction:* **X/5** --------
    # Each hypothesis runs from its bold header to the next (or end of doc).
    headers = list(re.finditer(r"(?m)^\*\*H\d+.*$", text))
    for i, hmatch in enumerate(headers):
        start = hmatch.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        scope = text[start:end]
        conv_m = re.search(r"[Cc]onviction:[\s*]*([12345])\s*/\s*5", scope)
        if not conv_m:
            continue
        ticker = _ticker_from_text(scope)
        if not ticker or ticker in seen_tickers:
            continue
        conviction = int(conv_m.group(1))
        # An explicit expected-return % overrides the conviction default.
        ret_m = re.search(r"[Ee]xpected\s+return.*?([+\-]?\d+\.?\d*)\s*%", scope)
        expected = (float(ret_m.group(1)) / 100.0) if ret_m else _CONVICTION_RETURN[conviction]
        label = hmatch.group(0).strip().strip("*")
        views.append({
            "ticker": ticker,
            "expected_return": expected,
            "confidence": conviction / 5.0,
            "derived": ret_m is None,
            "label": label[:120],
        })
        seen_tickers.add(ticker)
    return views


def current_portfolio_point(tickers: list[str]) -> dict | None:
    """(risk, return, sharpe) of the *current* market-value-weighted portfolio.

    Plotted as the highlighted dot against the efficient frontier. Uses the same
    annualized mean-return + sample-cov estimates as the optimizers so it's on the
    same axes.
    """
    from modules.finance.price_history import latest_price

    holdings = current_holdings()
    weights = {t: holdings.get(t, 0.0) * (latest_price(t) or 0.0) for t in tickers}
    total = sum(weights.values())
    if total <= 0:
        return None
    w = pd.Series({t: weights[t] / total for t in tickers})
    mu = expected_returns_mean(tickers)
    S = covariance_matrix(tickers)
    if mu.empty or S.empty:
        return None
    w = w.reindex(mu.index).fillna(0.0)
    ret = float(w @ mu)
    vol = float(np.sqrt(w.values @ S.values @ w.values))
    sharpe = (ret - 0.04) / vol if vol else None
    return {"return": ret, "risk": vol, "sharpe": sharpe,
            "weights": {k: round(float(v), 4) for k, v in w.items()}}


def optimization_signals() -> dict:
    """Compact current-vs-optimal summary for the Home 'optimization signals' block."""
    from modules.finance import risk
    from modules.finance.performance import portfolio_returns

    tickers = _resolve_tickers(None)
    if len(tickers) < 2:
        return {"available": False, "reason": "need at least 2 priced holdings"}

    returns = portfolio_returns()
    current_sharpe = risk.sharpe(returns) if not returns.empty else None
    current_conc = risk.concentration_metrics()

    ms = max_sharpe_portfolio(tickers)
    mv = min_variance_portfolio(tickers)
    max_sharpe_val = ms["performance"]["sharpe"] if ms.get("performance") else None

    # Effective N of the min-variance portfolio (diversification target).
    mv_weights = list(mv.get("weights", {}).values())
    hhi_mv = sum(w * w for w in mv_weights) if mv_weights else None
    eff_n_mv = round(1 / hhi_mv, 2) if hhi_mv else None

    gap = (max_sharpe_val - current_sharpe) if (max_sharpe_val is not None and current_sharpe is not None) else None
    return {
        "available": True,
        "current_sharpe": current_sharpe,
        "max_sharpe": max_sharpe_val,
        "sharpe_gap": round(gap, 3) if gap is not None else None,
        "current_effective_bets": current_conc.get("effective_n_bets"),
        "min_variance_effective_bets": eff_n_mv,
        "max_sharpe_weights": ms.get("weights", {}),
    }
