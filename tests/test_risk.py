"""Tests for risk.correlation_matrix_with_benchmarks + /risk/correlation, and the risk-free-rate
default behaviour of risk.sharpe / sortino / compute_all (Chunk 8). Synthetic, network-free.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import risk as risk_api
from core.config import BENCHMARKS, DEFAULT_RISK_FREE_RATE
from modules.finance import risk

N = 500
IDX = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=N)


def _series(seed, drift=0.0004, common=None, beta=0.0):
    rng = np.random.default_rng(seed)
    r = rng.normal(drift, 0.01, N)
    if common is not None:
        r = r + beta * common
    return pd.Series(r, index=IDX)


@pytest.fixture
def world(monkeypatch):
    market = np.random.default_rng(0).normal(0, 0.01, N)
    series = {
        BENCHMARKS["MSCI_WORLD"]["ticker"]: _series(1, common=market, beta=1.0),
        BENCHMARKS["SPY"]["ticker"]: _series(2, common=market, beta=1.0),
        BENCHMARKS["DAX"]["ticker"]: _series(3, common=market, beta=0.7),
        BENCHMARKS["STOXX_600"]["ticker"]: _series(4, common=market, beta=0.7),
        "AAA": _series(5, common=market, beta=1.2),
        "BBB": _series(6),
    }
    monkeypatch.setattr(risk, "get_returns", lambda t, freq="D": series.get(t, pd.Series(dtype="float64")))
    return series


# --- correlation with benchmarks ------------------------------------------------------------------------

def test_benchmarks_are_prepended_by_name(world):
    m = risk.correlation_matrix_with_benchmarks(["AAA", "BBB"])

    assert list(m.columns) == ["MSCI World", "S&P 500", "DAX 40", "STOXX Europe 600", "AAA", "BBB"]
    assert list(m.index) == list(m.columns)  # N x N, same order on both axes


def test_matrix_is_symmetric_with_unit_diagonal(world):
    m = risk.correlation_matrix_with_benchmarks(["AAA", "BBB"]).to_numpy()
    assert m.shape == (6, 6) and np.allclose(m, m.T) and np.allclose(np.diag(m), 1.0)


def test_holdings_can_be_excluded_from_benchmarks_and_vice_versa(world):
    without = risk.correlation_matrix_with_benchmarks(["AAA", "BBB"], include_benchmarks=False)
    assert list(without.columns) == ["AAA", "BBB"]
    # empty ledger: the four benchmarks alone still give a 4x4 matrix
    only_bench = risk.correlation_matrix_with_benchmarks([])
    assert only_bench.shape == (4, 4)
    assert risk.correlation_matrix_with_benchmarks([], include_benchmarks=False).empty


def test_adding_benchmarks_does_not_change_how_holdings_correlate(world):
    """Same dropna alignment: on an identical window, AAA/BBB correlation is unchanged."""
    plain = risk.correlation_matrix(["AAA", "BBB"]).loc["AAA", "BBB"]
    with_b = risk.correlation_matrix_with_benchmarks(["AAA", "BBB"]).loc["AAA", "BBB"]
    assert with_b == pytest.approx(plain)


def test_a_held_benchmark_ticker_stays_a_separate_row_from_the_benchmark(world):
    m = risk.correlation_matrix_with_benchmarks([BENCHMARKS["MSCI_WORLD"]["ticker"]])
    assert "MSCI World" in m.columns and BENCHMARKS["MSCI_WORLD"]["ticker"] in m.columns
    assert m.loc["MSCI World", BENCHMARKS["MSCI_WORLD"]["ticker"]] == pytest.approx(1.0)


def test_correlation_endpoint_lists_benchmark_labels(world, monkeypatch):
    monkeypatch.setattr(risk_api, "current_holdings", lambda: {"AAA": 1.0, "BBB": 2.0})
    app = FastAPI()
    app.include_router(risk_api.router, prefix="/api/finance")
    client = TestClient(app)

    body = client.get("/api/finance/risk/correlation").json()   # include_benchmarks defaults to true
    assert body["tickers"][:4] == ["MSCI World", "S&P 500", "DAX 40", "STOXX Europe 600"]
    assert body["benchmarks"] == ["MSCI World", "S&P 500", "DAX 40", "STOXX Europe 600"]
    assert body["matrix"][0]["ticker"] == "MSCI World" and body["matrix"][0]["MSCI World"] == 1.0

    off = client.get("/api/finance/risk/correlation?include_benchmarks=false").json()
    assert off["tickers"] == ["AAA", "BBB"] and off["benchmarks"] == []


# --- risk-free rate ------------------------------------------------------------------------------------------

def test_default_risk_free_rate_is_the_hardcoded_four_percent(world):
    r = world["AAA"]
    assert DEFAULT_RISK_FREE_RATE == 0.04
    assert risk.sharpe(r) == pytest.approx(risk.sharpe(r, 0.04))
    assert risk.sortino(r) == pytest.approx(risk.sortino(r, 0.04))


def test_a_higher_risk_free_rate_lowers_sharpe_and_sortino(world):
    r = world["AAA"]
    assert risk.sharpe(r, 0.0) > risk.sharpe(r, 0.04) > risk.sharpe(r, 0.10)
    assert risk.sortino(r, 0.0) > risk.sortino(r, 0.04) > risk.sortino(r, 0.10)


def test_compute_all_uses_the_supplied_rate_and_defaults_to_four_percent(world, monkeypatch):
    monkeypatch.setattr(risk, "portfolio_returns", lambda *a, **k: world["AAA"])
    monkeypatch.setattr(risk, "current_holdings", lambda: {"AAA": 1.0})
    monkeypatch.setattr(risk, "concentration_metrics", lambda *a, **k: {})

    default = risk.compute_all("MSCI_WORLD")
    explicit = risk.compute_all("MSCI_WORLD", risk_free=0.04)
    high = risk.compute_all("MSCI_WORLD", risk_free=0.10)

    assert default["sharpe"] == pytest.approx(explicit["sharpe"])
    assert high["sharpe"] < default["sharpe"] and high["sortino"] < default["sortino"]
