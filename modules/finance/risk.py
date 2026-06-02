"""Portfolio risk analytics (Phase 15a, Category C).

Volatility, risk-adjusted ratios (Sharpe / Sortino / Calmar), drawdown anatomy,
beta, Value-at-Risk (parametric / historical / Cornish-Fisher), expected
shortfall (CVaR), a cross-asset correlation matrix, and concentration measures
(Herfindahl, top-N weight, effective number of bets).

All return-series inputs are daily simple returns. Functions degrade to ``None``
/ empty rather than raising when there isn't enough data.
"""
from __future__ import annotations

from typing import Optional

import empyrical as ep
import numpy as np
import pandas as pd
from scipy import stats

from core.config import BENCHMARKS, DEFAULT_BENCHMARK, get_logger
from modules.finance.positions import current_holdings
from modules.finance.price_history import get_closes, get_returns, latest_price
from modules.finance.performance import portfolio_returns

logger = get_logger(__name__)

TRADING_DAYS = 252


def _f(value) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def volatility(returns: pd.Series, window_days: int = 90) -> pd.Series:
    """Rolling annualized volatility (std × √252)."""
    return returns.rolling(window_days).std() * np.sqrt(TRADING_DAYS)


def annualized_vol(returns: pd.Series) -> Optional[float]:
    """Single annualized volatility figure over the whole series."""
    if returns.empty:
        return None
    return _f(returns.std() * np.sqrt(TRADING_DAYS))


def sharpe(returns: pd.Series, risk_free: float = 0.04) -> Optional[float]:
    if returns.empty:
        return None
    return _f(ep.sharpe_ratio(returns, risk_free=risk_free / TRADING_DAYS, annualization=TRADING_DAYS))


def sortino(returns: pd.Series, risk_free: float = 0.04) -> Optional[float]:
    if returns.empty:
        return None
    return _f(ep.sortino_ratio(returns, required_return=risk_free / TRADING_DAYS, annualization=TRADING_DAYS))


def calmar(returns: pd.Series) -> Optional[float]:
    if returns.empty:
        return None
    return _f(ep.calmar_ratio(returns, annualization=TRADING_DAYS))


def max_drawdown(returns: pd.Series) -> dict:
    """Worst peak-to-trough drawdown with peak/trough/recovery dates + duration."""
    if returns.empty:
        return {"magnitude": None, "peak_date": None, "trough_date": None,
                "recovery_date": None, "duration_days": None}
    cum = (1 + returns).cumprod()
    running_max = cum.cummax()
    drawdown = (cum - running_max) / running_max
    trough_idx = drawdown.idxmin()
    peak_idx = cum[:trough_idx].idxmax()
    after = cum[trough_idx:]
    recovery = after[after >= cum[peak_idx]]
    recovery_idx = recovery.index[0] if not recovery.empty else None
    return {
        "magnitude": _f(drawdown.min()),
        "peak_date": pd.Timestamp(peak_idx).date().isoformat(),
        "trough_date": pd.Timestamp(trough_idx).date().isoformat(),
        "recovery_date": pd.Timestamp(recovery_idx).date().isoformat() if recovery_idx is not None else None,
        "duration_days": int((pd.Timestamp(trough_idx) - pd.Timestamp(peak_idx)).days),
    }


def beta_vs(returns: pd.Series, benchmark_ticker: str) -> Optional[float]:
    bench = get_returns(benchmark_ticker)
    aligned = pd.concat([returns, bench], axis=1).dropna()
    if aligned.empty or len(aligned) < 2:
        return None
    return _f(ep.beta(aligned.iloc[:, 0], aligned.iloc[:, 1]))


# --- Value at Risk ----------------------------------------------------------

def var_parametric(returns: pd.Series, alpha: float = 0.05) -> Optional[float]:
    """Parametric (Gaussian) VaR — the loss not exceeded with prob 1−alpha."""
    if returns.empty:
        return None
    return _f(returns.mean() - stats.norm.ppf(1 - alpha) * returns.std())


def var_historical(returns: pd.Series, alpha: float = 0.05) -> Optional[float]:
    """Historical VaR — the empirical alpha-quantile of returns."""
    if returns.empty:
        return None
    return _f(returns.quantile(alpha))


def var_cornish_fisher(returns: pd.Series, alpha: float = 0.05) -> Optional[float]:
    """VaR adjusted for skew + excess kurtosis (Cornish-Fisher expansion)."""
    if returns.empty:
        return None
    z = stats.norm.ppf(alpha)
    s = stats.skew(returns)
    k = stats.kurtosis(returns)  # Fisher (excess) kurtosis
    z_cf = (z + (z**2 - 1) * s / 6 + (z**3 - 3 * z) * k / 24
            - (2 * z**3 - 5 * z) * s**2 / 36)
    return _f(returns.mean() + z_cf * returns.std())


def expected_shortfall(returns: pd.Series, alpha: float = 0.05) -> Optional[float]:
    """CVaR — mean loss in the worst alpha-tail of outcomes."""
    if returns.empty:
        return None
    threshold = returns.quantile(alpha)
    tail = returns[returns <= threshold]
    return _f(tail.mean()) if not tail.empty else None


def correlation_matrix(tickers: list[str]) -> pd.DataFrame:
    """Pairwise correlation of daily returns across tickers (dropna-aligned)."""
    series = {}
    for t in tickers:
        r = get_returns(t)
        if not r.empty:
            series[t] = r
    if not series:
        return pd.DataFrame()
    df = pd.DataFrame(series).dropna()
    return df.corr()


def concentration_metrics(holdings: Optional[dict] = None,
                          prices: Optional[dict] = None) -> dict:
    """Herfindahl index, effective number of bets, and top-N weights."""
    holdings = current_holdings() if holdings is None else holdings
    if prices is None:
        prices = {t: latest_price(t) or 0.0 for t in holdings}
    values = {t: holdings[t] * (prices.get(t) or 0.0) for t in holdings}
    total = sum(values.values())
    if total <= 0:
        return {"herfindahl_index": None, "effective_n_bets": None,
                "top_1_weight": None, "top_3_weight": None, "top_5_weight": None}
    weights = sorted((v / total for v in values.values()), reverse=True)
    herfindahl = sum(w**2 for w in weights)
    return {
        "herfindahl_index": round(herfindahl, 4),
        "effective_n_bets": round(1 / herfindahl, 2) if herfindahl > 0 else None,
        "top_1_weight": round(weights[0], 4) if weights else None,
        "top_3_weight": round(sum(weights[:3]), 4),
        "top_5_weight": round(sum(weights[:5]), 4),
    }


def compute_all(benchmark: str = DEFAULT_BENCHMARK, risk_free: float = 0.04) -> dict:
    """Bundle every risk metric for the API (JSON-safe)."""
    returns = portfolio_returns()
    if returns.empty:
        return {"available": False, "reason": "no priced holdings"}
    bench_ticker = BENCHMARKS.get(benchmark, BENCHMARKS[DEFAULT_BENCHMARK])["ticker"]
    vol = volatility(returns, 90).dropna()
    vol30 = volatility(returns, 30).dropna()
    vol12m = volatility(returns, TRADING_DAYS).dropna()
    return {
        "available": True,
        "benchmark": benchmark,
        "volatility": {
            "rolling_30d": _f(vol30.iloc[-1]) if not vol30.empty else None,
            "rolling_90d": _f(vol.iloc[-1]) if not vol.empty else None,
            "rolling_12m": _f(vol12m.iloc[-1]) if not vol12m.empty else None,
            "annualized": annualized_vol(returns),
        },
        "sharpe": sharpe(returns, risk_free),
        "sortino": sortino(returns, risk_free),
        "calmar": calmar(returns),
        "max_drawdown": max_drawdown(returns),
        "beta": beta_vs(returns, bench_ticker),
        "var": {
            "parametric_95": var_parametric(returns, 0.05),
            "parametric_99": var_parametric(returns, 0.01),
            "historical_95": var_historical(returns, 0.05),
            "historical_99": var_historical(returns, 0.01),
            "cornish_fisher_95": var_cornish_fisher(returns, 0.05),
            "cornish_fisher_99": var_cornish_fisher(returns, 0.01),
        },
        "expected_shortfall": {
            "cvar_95": expected_shortfall(returns, 0.05),
            "cvar_99": expected_shortfall(returns, 0.01),
        },
        "concentration": concentration_metrics(),
    }
