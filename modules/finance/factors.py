"""Fama-French factor regression + portfolio factor exposure (Phase 15b, Cat. E).

The spec calls for ``pandas-datareader``'s ``FamaFrenchReader``, but that library
is unusable under this project's pandas 3.0 (its ``deprecate_kwarg`` call breaks at
import) AND — because ``empyrical`` imports it lazily — installing it crashes the
entire 15a performance/risk layer. So the Ken French data library is fetched
**directly** here (zip → CSV parse), keeping the spec's public functions and
return shapes (``get_ff3_factors`` / ``ff3_regression`` /
``factor_exposure_decomposition``). Factors are cached to ``data/ff_cache/``.
"""
from __future__ import annotations

import io
import re
import zipfile
from datetime import date, timedelta

import pandas as pd

from core.config import DATA_DIR, get_logger
from modules.finance.performance import portfolio_returns

logger = get_logger(__name__)

FF_CACHE_DIR = DATA_DIR / "ff_cache"

# Ken French data library datasets per region (3-factor monthly).
_FF_URLS = {
    "US": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip",
    "Europe": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Europe_3_Factors_CSV.zip",
    "Global": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Global_3_Factors_CSV.zip",
}

_factor_cache: dict[str, pd.DataFrame] = {}


def _parse_ff_csv(raw: str) -> pd.DataFrame:
    """Parse the monthly block of a Ken French factors CSV into a DataFrame.

    Rows look like ``192607,   2.96,  -2.30,  -2.87,   0.22`` (date = YYYYMM, then
    Mkt-RF, SMB, HML, RF in percent). The annual block uses 4-digit years and is
    ignored. Returns columns ``[MKT, SMB, HML, RF]`` as decimals, month-end index.
    """
    rows: list[tuple] = []
    for line in raw.splitlines():
        m = re.match(r"^\s*(\d{6})\s*,(.+)$", line)
        if not m:
            continue
        parts = [p.strip() for p in m.group(2).split(",")]
        if len(parts) < 4:
            continue
        try:
            vals = [float(parts[i]) for i in range(4)]
        except ValueError:
            continue
        idx = pd.to_datetime(m.group(1), format="%Y%m") + pd.offsets.MonthEnd(0)
        rows.append((idx, *vals))
    if not rows:
        raise ValueError("No monthly factor rows parsed from Ken French CSV")
    df = pd.DataFrame(rows, columns=["date", "MKT", "SMB", "HML", "RF"]).set_index("date")
    return df / 100.0  # percent -> decimal


def get_ff3_factors(region: str = "US") -> pd.DataFrame:
    """Fama-French 3-factor monthly returns for a region (US / Europe / Global).

    Cached in-process and on disk (parquet, refreshed when >30 days stale).
    """
    region = region if region in _FF_URLS else "US"
    if region in _factor_cache:
        return _factor_cache[region]

    FF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = FF_CACHE_DIR / f"ff3_{region}.parquet"
    if cache_file.exists():
        age_days = (date.today() - date.fromtimestamp(cache_file.stat().st_mtime)).days
        if age_days < 30:
            df = pd.read_parquet(cache_file)
            _factor_cache[region] = df
            return df

    import requests

    logger.info("Downloading Ken French %s 3-factor data", region)
    resp = requests.get(_FF_URLS[region], timeout=30)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        raw = zf.read(csv_name).decode("latin-1")
    df = _parse_ff_csv(raw)
    df.to_parquet(cache_file)
    _factor_cache[region] = df
    return df


def ff3_regression(port_returns: pd.Series | None = None, region: str = "US") -> dict:
    """Fama-French 3-factor OLS regression on (monthly) portfolio returns.

    Returns alpha (monthly + annualized), the 3 factor betas, their t-stats, R²
    and the observation count. Defaults to the current portfolio's return series.
    """
    if port_returns is None:
        port_returns = portfolio_returns()
    if port_returns is None or port_returns.empty:
        return {"available": False, "reason": "no portfolio return series"}

    import statsmodels.api as sm

    factors = get_ff3_factors(region)
    monthly_port = (1 + port_returns).resample("ME").prod() - 1  # "ME" = month-end (pandas 2.2+)
    aligned = pd.concat([monthly_port, factors], axis=1).dropna()
    aligned.columns = ["port", "MKT", "SMB", "HML", "RF"]
    if len(aligned) < 6:
        return {"available": False, "reason": f"only {len(aligned)} aligned months (need ≥6)"}

    excess = aligned["port"] - aligned["RF"]
    X = sm.add_constant(aligned[["MKT", "SMB", "HML"]])
    model = sm.OLS(excess, X).fit()

    return {
        "available": True,
        "region": region,
        "alpha_monthly": float(model.params["const"]),
        "alpha_annual": float(model.params["const"] * 12),
        "beta_mkt": float(model.params["MKT"]),
        "beta_smb": float(model.params["SMB"]),
        "beta_hml": float(model.params["HML"]),
        "t_alpha": float(model.tvalues["const"]),
        "t_mkt": float(model.tvalues["MKT"]),
        "t_smb": float(model.tvalues["SMB"]),
        "t_hml": float(model.tvalues["HML"]),
        "r_squared": float(model.rsquared),
        "n_observations": int(model.nobs),
    }


def factor_exposure_decomposition(port_returns: pd.Series | None = None, region: str = "US") -> dict:
    """Share of portfolio variance attributable to each factor (+ idiosyncratic)."""
    if port_returns is None:
        port_returns = portfolio_returns()
    if port_returns is None or port_returns.empty:
        return {"available": False, "reason": "no portfolio return series"}

    regression = ff3_regression(port_returns, region)
    if not regression.get("available"):
        return regression

    factors = get_ff3_factors(region)
    # Annualized portfolio variance from monthly returns.
    monthly_port = (1 + port_returns).resample("ME").prod() - 1
    port_var = monthly_port.var() * 12
    if not port_var or port_var <= 0:
        return {"available": False, "reason": "degenerate portfolio variance"}

    contrib = {
        "market": (regression["beta_mkt"] ** 2 * factors["MKT"].var() * 12) / port_var,
        "size_smb": (regression["beta_smb"] ** 2 * factors["SMB"].var() * 12) / port_var,
        "value_hml": (regression["beta_hml"] ** 2 * factors["HML"].var() * 12) / port_var,
    }
    contrib = {k: float(max(0.0, v)) for k, v in contrib.items()}
    contrib["idiosyncratic"] = float(max(0.0, 1 - sum(contrib.values())))
    return {"available": True, "region": region, "regression": regression,
            "variance_decomposition": contrib}
