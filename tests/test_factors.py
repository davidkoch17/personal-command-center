"""Tests for the Chunk 8 factor additions: rolling factor betas and the portfolio-vs-benchmark
loadings comparison. Synthetic Ken French-style monthly factors; no downloads, no cache.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import factors as factors_api
from core.config import BENCHMARKS
from modules.finance import factors as fx

MONTHS = 120
ME = pd.date_range("2016-01-31", periods=MONTHS, freq="ME")
BENCH = BENCHMARKS["MSCI_WORLD"]["ticker"]


def _factors(ff5=False, seed=1):
    rng = np.random.default_rng(seed)
    cols = ["MKT", "SMB", "HML"] + (["RMW", "CMA"] if ff5 else [])
    df = pd.DataFrame(rng.normal(0.006, 0.035, (MONTHS, len(cols))), index=ME, columns=cols)
    df["RF"] = 0.002
    return df


def _daily_from_monthly(monthly: pd.Series) -> pd.Series:
    """A daily series that compounds back to ``monthly``: the whole month's return on its last business day."""
    idx = pd.bdate_range(monthly.index[0] - pd.offsets.MonthEnd(1) + pd.Timedelta(days=1), monthly.index[-1])
    daily = pd.Series(0.0, index=idx)
    for me, r in monthly.items():
        last = daily.index[daily.index <= me][-1]
        daily.loc[last] = r
    return daily


def _port(frame, betas, alpha=0.001, seed=2, cols=("MKT", "SMB", "HML")):
    """Monthly portfolio return = RF + alpha + sum(beta * factor) + small noise."""
    noise = np.random.default_rng(seed).normal(0, 0.004, len(frame))
    exposure = sum(b * frame[c] for c, b in zip(cols, betas))
    return frame["RF"] + alpha + exposure + noise


# --- rolling betas ---------------------------------------------------------------------------------

def test_rolling_betas_recover_constant_exposures():
    f = _factors()
    monthly = _port(f, (0.9, 0.3, -0.2))

    out = fx.rolling_factor_betas(_daily_from_monthly(monthly), f, window_months=36)

    assert out["available"] and out["window_months"] == 36 and out["model"] == "ff3"
    assert list(out["series"]) == ["mkt", "smb", "hml"]
    assert len(out["dates"]) == MONTHS - 36 + 1 and out["dates"] == sorted(out["dates"])
    assert all(len(v) == len(out["dates"]) for v in out["series"].values())
    assert np.mean(out["series"]["mkt"]) == pytest.approx(0.9, abs=0.08)
    assert np.mean(out["series"]["smb"]) == pytest.approx(0.3, abs=0.12)
    assert np.mean(out["series"]["hml"]) == pytest.approx(-0.2, abs=0.12)


def test_rolling_betas_track_a_regime_change():
    """Market beta 0.5 for the first 5 years, 1.5 for the last 5: the rolling series must move."""
    f = _factors(seed=5)
    monthly = pd.concat([_port(f.iloc[:60], (0.5, 0, 0)), _port(f.iloc[60:], (1.5, 0, 0), seed=9)])

    out = fx.rolling_factor_betas(_daily_from_monthly(monthly), f, window_months=36)

    assert out["series"]["mkt"][0] == pytest.approx(0.5, abs=0.2)     # window entirely in regime 1
    assert out["series"]["mkt"][-1] == pytest.approx(1.5, abs=0.2)    # window entirely in regime 2
    assert out["series"]["mkt"][-1] - out["series"]["mkt"][0] > 0.6


def test_rolling_betas_ff5_has_five_series():
    f = _factors(ff5=True)
    monthly = _port(f, (1.0, 0.2, 0.1, 0.4, -0.3), cols=("MKT", "SMB", "HML", "RMW", "CMA"))
    out = fx.rolling_factor_betas(_daily_from_monthly(monthly), f, 36, model="ff5")
    assert list(out["series"]) == ["mkt", "smb", "hml", "rmw", "cma"]
    assert np.mean(out["series"]["rmw"]) == pytest.approx(0.4, abs=0.15)


def test_rolling_betas_need_a_full_window_and_data():
    f = _factors()
    short = _daily_from_monthly(_port(f, (1, 0, 0)).iloc[:30])
    out = fx.rolling_factor_betas(short, f, 36)
    assert out["available"] is False and "need ≥36" in out["reason"]
    assert fx.rolling_factor_betas(pd.Series(dtype="float64"), f)["available"] is False


# --- benchmark loadings ------------------------------------------------------------------------------

@pytest.fixture
def world(monkeypatch):
    f = _factors()
    port_monthly = _port(f, (0.8, 0.4, 0.2), seed=3)
    bench_monthly = _port(f, (1.0, 0.0, 0.0), alpha=0.0, seed=4)
    series = {BENCH: _daily_from_monthly(bench_monthly)}
    monkeypatch.setattr(fx, "get_ff3_factors", lambda region="US": f)
    monkeypatch.setattr(fx, "get_returns", lambda t, freq="D": series.get(t, pd.Series(dtype="float64")))
    monkeypatch.setattr(fx, "portfolio_returns", lambda *a, **k: _daily_from_monthly(port_monthly))
    return f, series


def test_benchmark_factor_loadings_recovers_the_benchmarks_betas(world):
    out = fx.benchmark_factor_loadings(BENCH, region="US", period="all")

    assert out["available"] and out["model"] == "ff3"
    assert out["betas"]["mkt"] == pytest.approx(1.0, abs=0.05)
    assert abs(out["betas"]["smb"]) < 0.08 and abs(out["betas"]["hml"]) < 0.08
    assert 0.9 < out["r_squared"] <= 1.0 and out["n_observations"] > 100


def test_benchmark_factor_loadings_unavailable_without_history(world):
    assert fx.benchmark_factor_loadings("NOPE")["available"] is False


def test_loadings_comparison_shows_portfolio_and_benchmark_side_by_side(world):
    out = fx.factor_loadings_comparison("MSCI_WORLD", region="US", period="all")
    row = {r["factor"]: r for r in out["factors"]}

    assert out["available"] and out["benchmark_name"] == "MSCI World" and [r["factor"] for r in out["factors"]] == ["MKT", "SMB", "HML"]
    assert row["MKT"]["portfolio"] == pytest.approx(0.8, abs=0.08) and row["MKT"]["benchmark"] == pytest.approx(1.0, abs=0.08)
    assert row["SMB"]["portfolio"] == pytest.approx(0.4, abs=0.12) and abs(row["SMB"]["benchmark"]) < 0.1
    assert set(out["portfolio"]) == {"alpha_annual", "r_squared"}


def test_comparison_regresses_both_on_the_same_months(world, monkeypatch):
    f, series = world
    late = series[BENCH].loc["2020-01-01":]  # benchmark history starts 4 years later than the portfolio's
    monkeypatch.setattr(fx, "get_returns", lambda t, freq="D": late if t == BENCH else pd.Series(dtype="float64"))

    out = fx.factor_loadings_comparison("MSCI_WORLD", "US", "all")

    assert out["available"] and out["n_observations"] <= MONTHS - 48 + 1  # the shorter series sets the window


def test_comparison_reports_why_it_is_unavailable(world, monkeypatch):
    monkeypatch.setattr(fx, "portfolio_returns", lambda *a, **k: pd.Series(dtype="float64"))
    assert fx.factor_loadings_comparison("SPY")["reason"] == "no portfolio return series"


def test_factor_endpoints(world):
    app = FastAPI()
    app.include_router(factors_api.router, prefix="/api/finance")
    client = TestClient(app)

    roll = client.get("/api/finance/factors/rolling?region=US&model=ff3&window=36").json()
    assert roll["available"] and roll["region"] == "US" and len(roll["dates"]) == MONTHS - 36 + 1

    cmp_ = client.get("/api/finance/factors/loadings-comparison?benchmark=MSCI_WORLD&region=US").json()
    assert cmp_["available"] and cmp_["benchmark"] == "MSCI_WORLD" and len(cmp_["factors"]) == 3
    assert client.get("/api/finance/factors/rolling?window=3").status_code == 422
