"""Tests for performance.alpha_per_holding and GET /performance/alpha-per-holding (Chunk 8).

Synthetic returns with known beta/alpha; monkeypatched, network-free.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import performance as perf_api
from core.config import BENCHMARKS, DEFAULT_RISK_FREE_RATE
from modules.finance import performance as perf

N = 800
IDX = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=N)
BENCH = BENCHMARKS["MSCI_WORLD"]["ticker"]


@pytest.fixture
def world(monkeypatch):
    rng = np.random.default_rng(4)
    m = pd.Series(rng.normal(0.0005, 0.010, N), index=IDX)
    series = {
        BENCH: m,
        "HI": 0.0004 + 1.5 * m + pd.Series(rng.normal(0, 0.004, N), index=IDX),   # beta 1.5, alpha +0.0004/day
        "LOW": -0.0003 + 0.6 * m + pd.Series(rng.normal(0, 0.004, N), index=IDX),  # beta 0.6, alpha -0.0003/day
        "SHORT": (0.0002 + m).iloc[-20:],                                          # too little history
    }
    monkeypatch.setattr(perf, "get_returns", lambda t, freq="D": series.get(t, pd.Series(dtype="float64")))
    return series


def test_alpha_beta_r2_recovered(world):
    out = perf.alpha_per_holding(["HI", "LOW"], BENCH, "all", risk_free=0.0)

    assert out["HI"]["beta"] == pytest.approx(1.5, abs=0.06) and out["LOW"]["beta"] == pytest.approx(0.6, abs=0.06)
    # daily alpha x 252 (rf = 0): +0.0004*252 ~ +10%, -0.0003*252 ~ -7.6%
    assert out["HI"]["alpha"] == pytest.approx(0.0004 * 252, abs=0.05) and out["HI"]["alpha"] > 0
    assert out["LOW"]["alpha"] == pytest.approx(-0.0003 * 252, abs=0.05) and out["LOW"]["alpha"] < 0
    assert 0.5 < out["HI"]["r_squared"] < 1 and out["HI"]["n"] == N


def test_alpha_uses_the_shared_risk_free_rate(world):
    """alpha(rf) = alpha(0) - (1 - beta) * rf  — a beta > 1 asset gains from a higher rf."""
    a0 = perf.alpha_per_holding(["HI"], BENCH, "all", risk_free=0.0)["HI"]
    a4 = perf.alpha_per_holding(["HI"], BENCH, "all", risk_free=0.04)["HI"]

    assert a4["alpha"] == pytest.approx(a0["alpha"] - (1 - a0["beta"]) * 0.04)
    assert a4["beta"] == pytest.approx(a0["beta"])  # beta doesn't depend on rf


def test_default_risk_free_rate_is_the_shared_four_percent(world):
    default = perf.alpha_per_holding(["HI"], BENCH, "all")["HI"]["alpha"]
    explicit = perf.alpha_per_holding(["HI"], BENCH, "all", risk_free=DEFAULT_RISK_FREE_RATE)["HI"]["alpha"]
    assert DEFAULT_RISK_FREE_RATE == 0.04 and default == pytest.approx(explicit)


def test_short_history_is_none_not_a_bogus_estimate(world):
    out = perf.alpha_per_holding(["SHORT", "GHOST"], BENCH, "all")
    assert out["SHORT"]["alpha"] is None and out["SHORT"]["n"] == 20
    assert out["GHOST"] == {"alpha": None, "beta": None, "r_squared": None, "n": 0}


def test_period_slices_each_tickers_own_history(world):
    full = perf.alpha_per_holding(["HI"], BENCH, "all")["HI"]
    year = perf.alpha_per_holding(["HI"], BENCH, "1y")["HI"]
    assert year["n"] < full["n"] and year["n"] > 200 and year["alpha"] != pytest.approx(full["alpha"], abs=1e-6)


def test_alpha_per_holding_endpoint(world, monkeypatch):
    monkeypatch.setattr(perf, "current_holdings", lambda: {"HI": 1.0, "LOW": 1.0})
    app = FastAPI()
    app.include_router(perf_api.router, prefix="/api/finance")
    client = TestClient(app)

    body = client.get("/api/finance/performance/alpha-per-holding?benchmark=MSCI_WORLD&period=ALL").json()

    assert body["benchmark"] == "MSCI_WORLD" and body["period"] == "all" and body["risk_free_rate"] == 0.04
    assert set(body["holdings"]) == {"HI", "LOW"} and body["holdings"]["HI"]["alpha"] > body["holdings"]["LOW"]["alpha"]
    assert client.get("/api/finance/performance/alpha-per-holding?rfr=0.1").json()["risk_free_rate"] == 0.1
    assert client.get("/api/finance/performance/alpha-per-holding?rfr=0.9").status_code == 422
