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

from core.config import DEFAULT_BENCHMARK, DEFAULT_RISK_FREE_RATE, BENCHMARKS, get_logger
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
    risk_free: float = DEFAULT_RISK_FREE_RATE,
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


def capm_mu_from_returns(rets: pd.DataFrame, market: pd.Series, risk_free: float = DEFAULT_RISK_FREE_RATE) -> pd.Series:
    """CAPM-implied annual expected returns: E[r_i] = rf + beta_i * (E[r_m] - rf).

    ``rets`` is the daily-returns matrix of the assets, ``market`` the daily
    returns of the benchmark standing in for "the market". Beta and the market
    mean use the dates both share (inner join). Arithmetic annualization —
    identical to ``pypfopt.expected_returns.capm_return(..., compounding=False)``
    on gap-free data (asserted in tests).
    """
    reg = capm_regression(rets, market)
    if reg is None:
        return pd.Series(dtype="float64")
    stats, market_mean_daily = reg
    return risk_free + stats["beta"] * (market_mean_daily * TRADING_DAYS - risk_free)


def capm_regression(rets: pd.DataFrame, market: pd.Series) -> tuple[pd.DataFrame, float] | None:
    """Single-index regression of each asset on the market, in daily terms.

    Returns ``(stats, market_mean_daily)`` where ``stats`` has one row per asset
    with ``beta`` (cov/var), ``alpha_daily`` (Jensen intercept of the raw-return
    regression, ``mean_i - beta * mean_m``) and ``mean_daily``; ``None`` when there
    is too little overlap or the market has no variance. This is the *one* place
    beta lives: the optimizer's CAPM mu, the Security Market Line and the return
    decomposition all call it, so they can never disagree about a beta.
    """
    joined = rets.join(market.rename("__mkt__"), how="inner").dropna()
    if len(joined) < 30:
        return None
    m = joined["__mkt__"]
    var = m.var()
    if not var:
        return None
    assets = joined.drop(columns="__mkt__")
    beta = assets.apply(lambda c: c.cov(m)) / var
    mean_daily = assets.mean()
    market_mean_daily = float(m.mean())
    stats = pd.DataFrame({
        "beta": beta,
        "alpha_daily": mean_daily - beta * market_mean_daily,
        "mean_daily": mean_daily,
    })
    return stats, market_mean_daily


def mu_cov(
    tickers: list[str],
    benchmark_ticker: Optional[str] = None,
    risk_free: float = DEFAULT_RISK_FREE_RATE,
    lookback_years: int = 5,
) -> tuple[pd.Series, pd.DataFrame]:
    """The single (mu, Sigma) source for the Optimization tab.

    With ``benchmark_ticker`` set, mu is CAPM-implied against that benchmark, so
    the frontier, the tangency star, the current-portfolio marker, the
    constrained overlay and the distance-from-frontier callout all consume the
    *same* vector and cannot disagree. ``benchmark_ticker=None`` keeps the
    historical-mean mu for the callers that never moved to CAPM (Home
    optimization signals). Sigma is always the sample covariance.
    """
    S = covariance_matrix(tickers, lookback_years)
    if benchmark_ticker is None:
        mu = expected_returns_mean(tickers, lookback_years)
    else:
        rets = get_returns_matrix(tickers, lookback_years)
        market = get_returns(benchmark_ticker)
        if rets.empty or market.empty:
            mu = pd.Series(dtype="float64")
        else:
            mu = capm_mu_from_returns(rets, market, risk_free)
    if mu.empty or S.empty:
        return pd.Series(dtype="float64"), pd.DataFrame()
    common = [t for t in S.index if t in mu.index]
    return mu.reindex(common), S.reindex(index=common, columns=common)


def _perf_dict(perf: tuple) -> dict:
    """Normalize PyPortfolioOpt's (ret, vol, sharpe) tuple to a labelled dict."""
    return {
        "expected_return": float(perf[0]),
        "volatility": float(perf[1]),
        "sharpe": float(perf[2]),
    }


def efficient_frontier_points(tickers: list[str], n_points: int = 50, benchmark_ticker: Optional[str] = None) -> list[dict]:
    """Efficient frontier as (risk, return, weights) triplets, sampled from the
    minimum-variance return up to the highest reachable return."""
    mu, S = mu_cov(tickers, benchmark_ticker)
    if mu.empty or S.empty:
        return []
    return build_frontier_constrained(list(mu.index), mu, S, {}, n_points=n_points)["points"]


def min_variance_portfolio(tickers: list[str], constraints: dict | None = None, benchmark_ticker: Optional[str] = None) -> dict:
    from pypfopt import EfficientFrontier

    mu, S = mu_cov(tickers, benchmark_ticker)
    if mu.empty or S.empty:
        return {"weights": {}, "performance": None}
    ef = EfficientFrontier(mu, S)
    _apply_constraints(ef, constraints)
    ef.min_volatility()
    return {"weights": {k: round(float(v), 4) for k, v in ef.clean_weights().items()},
            "performance": _perf_dict(ef.portfolio_performance())}


def _max_sharpe_from(mu: pd.Series, S: pd.DataFrame, risk_free: float, constraints: dict | None = None) -> dict | None:
    """Tangency portfolio for a given (mu, S); ``None`` when max-Sharpe is
    unsolvable (e.g. every expected return is below the risk-free rate)."""
    from pypfopt import EfficientFrontier

    ef = EfficientFrontier(mu, S)
    _apply_constraints(ef, constraints)
    try:
        ef.max_sharpe(risk_free_rate=risk_free)
    except Exception as exc:  # noqa: BLE001
        logger.info("max_sharpe unsolvable: %s", exc)
        return None
    return {"weights": {k: round(float(v), 4) for k, v in ef.clean_weights().items()},
            "performance": _perf_dict(ef.portfolio_performance(risk_free_rate=risk_free))}


def max_sharpe_portfolio(
    tickers: list[str],
    risk_free: float = DEFAULT_RISK_FREE_RATE,
    constraints: dict | None = None,
    benchmark_ticker: Optional[str] = None,
) -> dict:
    from pypfopt import EfficientFrontier

    mu, S = mu_cov(tickers, benchmark_ticker, risk_free)
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


def current_portfolio_point(tickers: list[str], benchmark_ticker: Optional[str] = None) -> dict | None:
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
    mu, S = mu_cov(tickers, benchmark_ticker)
    if mu.empty or S.empty:
        return None
    w = w.reindex(mu.index).fillna(0.0)
    ret = float(w @ mu)
    vol = float(np.sqrt(w.values @ S.values @ w.values))
    sharpe = (ret - DEFAULT_RISK_FREE_RATE) / vol if vol else None
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


# ============================================================
# Chunk 3 — constraint modal (bucket caps / position bounds /
# concentration / currency / vol budget) + CML / distance-from-frontier.
# ============================================================

# Order the binding-constraint search drops sections in — loosest/most-likely
# to be the culprit first. Not load-bearing for correctness, just search order.
_SECTION_ORDER = ["vol_budget", "concentration", "currency_caps", "position_bounds", "bucket_caps"]


def _ticker_bucket_map(tickers: list[str]) -> dict[str, str]:
    """{ticker: resolved bucket}, via Chunk 2.5's resolve_bucket — no new
    ticker->bucket mapping logic lives here."""
    from modules.finance.buckets import resolve_bucket

    return {t: resolve_bucket(t) for t in tickers}


def _build_constrained_ef(mu: pd.Series, S: pd.DataFrame, tickers: list[str], constraints: dict):
    """Fresh EfficientFrontier with every *enabled* constraint-modal section
    applied. A section key that's absent or ``None`` in ``constraints`` means
    that toggle is off in the UI and is simply never added to the solver —
    this is what lets "isolate which constraint drives the Sharpe delta" work:
    the frontend just omits whichever sections are toggled off.
    """
    from pypfopt import EfficientFrontier
    import cvxpy as cp

    position_bounds = constraints.get("position_bounds")
    if position_bounds:
        weight_bounds = [
            (
                float((position_bounds.get(t) or {}).get("min") or 0.0),
                float((position_bounds.get(t) or {}).get("max") or 1.0),
            )
            for t in tickers
        ]
    else:
        weight_bounds = (0.0, 1.0)

    ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)

    bucket_caps = constraints.get("bucket_caps")
    if bucket_caps:
        bucket_map = _ticker_bucket_map(tickers)
        sector_lower = {b: float(v["min"]) for b, v in bucket_caps.items() if v.get("min") is not None}
        sector_upper = {b: float(v["max"]) for b, v in bucket_caps.items() if v.get("max") is not None}
        if sector_lower or sector_upper:
            ef.add_sector_constraints(bucket_map, sector_lower, sector_upper)

    concentration = constraints.get("concentration")
    if concentration:
        if concentration.get("max_single") is not None:
            cap = float(concentration["max_single"])
            ef.add_constraint(lambda w: w <= cap)
        if concentration.get("max_top5") is not None:
            top5 = float(concentration["max_top5"])
            k = min(5, len(tickers))
            ef.add_constraint(lambda w: cp.sum_largest(w, k) <= top5)
        if concentration.get("hhi_cap") is not None:
            hhi = float(concentration["hhi_cap"])
            ef.add_constraint(lambda w: cp.sum_squares(w) <= hhi)

    currency_caps = constraints.get("currency_caps")
    if currency_caps:
        from modules.finance.price_history import quote_currency

        idx_by_ccy: dict[str, list[int]] = {}
        for i, t in enumerate(tickers):
            idx_by_ccy.setdefault(quote_currency(t).upper(), []).append(i)
        for ccy, cap in currency_caps.items():
            if cap is None:
                continue
            idxs = idx_by_ccy.get(ccy.upper(), [])
            if idxs:
                ef.add_constraint(lambda w, idxs=idxs, cap=float(cap): cp.sum([w[i] for i in idxs]) <= cap)

    vol_budget = constraints.get("vol_budget")
    if vol_budget and vol_budget.get("max_vol") is not None:
        max_vol_sq = float(vol_budget["max_vol"]) ** 2
        ef.add_constraint(lambda w: cp.quad_form(w, S.values) <= max_vol_sq)

    return ef


def _find_binding_constraint(mu: pd.Series, S: pd.DataFrame, tickers: list[str], constraints: dict) -> Optional[str]:
    """Best-effort localization of *which* constraint section makes the set
    infeasible: drop one section at a time and retry min_volatility; the first
    removal that becomes feasible again is reported. This is a coarse,
    section-level heuristic (at most 5 extra solves) — PyPortfolioOpt/cvxpy
    don't reliably surface which single constraint an infeasible problem
    violated, so there's no dual-value read to fall back on here.
    """
    for key in _SECTION_ORDER:
        if not constraints.get(key):
            continue
        relaxed = {k: v for k, v in constraints.items() if k != key}
        try:
            ef = _build_constrained_ef(mu, S, tickers, relaxed)
            ef.min_volatility()
            return key
        except Exception:  # noqa: BLE001
            continue
    return None


def _max_feasible_return(mu: pd.Series, S: pd.DataFrame, tickers: list[str], constraints: dict) -> Optional[float]:
    """Highest annualized return reachable under ``constraints`` (a linear
    program over the same constraint set), or ``None`` if the solve fails."""
    try:
        ef = _build_constrained_ef(mu, S, tickers, constraints)
        mu_vals = mu.reindex(tickers).values
        ef.convex_objective(lambda w: -(w @ mu_vals))
        return float(ef.portfolio_performance()[0])
    except Exception as exc:  # noqa: BLE001
        logger.info("Max-feasible-return solve failed: %s", exc)
        return None


def build_frontier_constrained(
    tickers: list[str],
    mu: pd.Series,
    S: pd.DataFrame,
    constraints: dict,
    n_points: int = 30,
    risk_free: float = DEFAULT_RISK_FREE_RATE,
) -> dict:
    """Constrained efficient frontier honoring the constraint modal's five
    independently-toggleable sections (D8). Same point/tangency/mvp shape as
    the unconstrained :func:`efficient_frontier_points` family, plus
    ``feasible`` and (when infeasible) a best-effort ``binding_constraint``.
    """
    if mu.empty or S.empty:
        return {"points": [], "tangency": None, "mvp": None, "feasible": False,
                "binding_constraint": None, "reason": "no priced holdings"}

    try:
        ef = _build_constrained_ef(mu, S, tickers, constraints)
        ef.min_volatility()
        mvp = {"weights": {k: round(float(v), 4) for k, v in ef.clean_weights().items()},
               "performance": _perf_dict(ef.portfolio_performance())}
    except Exception as exc:  # noqa: BLE001 — infeasible constraint set
        logger.info("Constrained min_volatility infeasible: %s", exc)
        binding = _find_binding_constraint(mu, S, tickers, constraints)
        reason = "no feasible portfolio under these constraints"
        if binding:
            reason += f" — relax {binding.replace('_', ' ')}"
        return {"points": [], "tangency": None, "mvp": None, "feasible": False,
                "binding_constraint": binding, "reason": reason}

    try:
        ef = _build_constrained_ef(mu, S, tickers, constraints)
        ef.max_sharpe(risk_free_rate=risk_free)
        tangency = {"weights": {k: round(float(v), 4) for k, v in ef.clean_weights().items()},
                    "performance": _perf_dict(ef.portfolio_performance(risk_free_rate=risk_free))}
    except Exception as exc:  # noqa: BLE001 — feasible region exists but no reachable max-sharpe optimum (rare)
        logger.info("Constrained max_sharpe failed despite a feasible region: %s", exc)
        tangency = None

    # Sample targets across the *feasible* return range — from the constrained
    # min-variance return up to the highest return the constraint set allows —
    # rather than the raw mu range, most of which is unreachable once bucket caps
    # etc. bind (that left only a handful of points and stopped short of the ★).
    lo = mvp["performance"]["expected_return"]
    hi = _max_feasible_return(mu, S, tickers, constraints)
    if hi is None or hi <= lo:
        hi = float(mu.max())
    else:
        # A target exactly at the max-return vertex is numerically infeasible
        # (solver tolerance) and would silently drop the last point — back off 1bp.
        hi -= 1e-4
    points: list[dict] = []
    for target in np.linspace(lo, hi, n_points):
        try:
            ef = _build_constrained_ef(mu, S, tickers, constraints)
            ef.efficient_return(target_return=float(target))
            perf = ef.portfolio_performance()
            points.append({
                "target_return": float(target),
                "risk": float(perf[1]),
                "return": float(perf[0]),
                "sharpe": float(perf[2]),
                "weights": {k: round(float(v), 4) for k, v in ef.clean_weights().items()},
            })
        except Exception:  # noqa: BLE001 — infeasible individual targets are simply skipped
            continue

    return {"points": points, "tangency": tangency, "mvp": mvp,
            "feasible": True, "binding_constraint": None, "reason": None}


def compute_distance_from_frontier(
    tickers: list[str],
    current_weights: dict[str, float],
    mu: pd.Series,
    S: pd.DataFrame,
    risk_free: float = DEFAULT_RISK_FREE_RATE,
) -> dict:
    """Current-portfolio Sharpe vs. the tangency Sharpe (B2).

    ``mu``/``S`` must be the very vectors the frontier chart was built from
    (:func:`mu_cov` with the selected benchmark) and the tangency is solved by
    the same :func:`_max_sharpe_from` the chart's star uses, so this callout and
    the chart agree by construction — both are CAPM against one benchmark.
    """
    if not tickers or mu.empty or S.empty:
        return {"available": False, "reason": "no priced holdings"}

    common = [t for t in tickers if t in mu.index and t in S.index]
    w = pd.Series({t: current_weights.get(t, 0.0) for t in common})
    total = w.sum()
    if not common or total <= 0:
        return {"available": False, "reason": "no priced holdings"}
    w = w / total

    mu_c = mu.reindex(common)
    S_c = S.reindex(index=common, columns=common)
    port_ret = float(w @ mu_c)
    port_vol = float(np.sqrt(w.values @ S_c.values @ w.values))
    portfolio_sharpe = (port_ret - risk_free) / port_vol if port_vol else None

    tangency = _max_sharpe_from(mu_c, S_c, risk_free)
    if tangency is None:
        return {"available": False, "reason": "could not solve for the tangency portfolio"}
    perf = tangency["performance"]

    delta_bps = (
        round((portfolio_sharpe - perf["sharpe"]) * 10000, 1) if portfolio_sharpe is not None else None
    )
    return {
        "available": True,
        "portfolio_sharpe": round(portfolio_sharpe, 4) if portfolio_sharpe is not None else None,
        "tangency_sharpe": round(perf["sharpe"], 4),
        "delta_bps": delta_bps,
        "portfolio_vol": round(port_vol, 4),
        "tangency_vol": round(perf["volatility"], 4),
        "risk_free_rate": risk_free,
    }
