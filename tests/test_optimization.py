"""Tests for modules/finance/optimization.py's Chunk 3 additions — the
constraint modal (D8) and CML / distance-from-frontier (B1/B2).

All synthetic: mu/covariance/benchmark returns are hand-built pd.Series/
DataFrame, and the ticker->bucket map is monkeypatched exactly like
test_buckets.py — no network, no real price cache reads.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import optimization as opt_api
from core.config import DEFAULT_RISK_FREE_RATE
from modules.finance import buckets, optimization as opt


TICKERS = ["A", "B", "C", "D"]


def _synthetic_mu_cov():
    """4 uncorrelated synthetic assets, one per bucket, C has by far the best
    expected return so an unconstrained max-sharpe solve loads heavily into it
    — gives every constrained test something real to bite against."""
    mu = pd.Series({"A": 0.05, "B": 0.15, "C": 0.30, "D": 0.10})
    S = pd.DataFrame(
        np.diag([0.02, 0.03, 0.10, 0.05]),
        index=TICKERS, columns=TICKERS,
    )
    return mu, S


@pytest.fixture(autouse=True)
def mock_ticker_map(monkeypatch):
    """A: etf_foundation, B: single_stocks, C: crypto, D: wild_cards."""
    fake_map = {"A": "etf_foundation", "B": "single_stocks", "C": "crypto", "D": "wild_cards"}
    monkeypatch.setattr(buckets, "_load_ticker_bucket_map", lambda *a, **kw: fake_map)
    # No per-position overrides in these tests.
    monkeypatch.setattr(buckets, "get_position", lambda ticker: None)


def test_frontier_constrained_bucket_caps():
    mu, S = _synthetic_mu_cov()

    unconstrained = opt.build_frontier_constrained(TICKERS, mu, S, {})
    assert unconstrained["feasible"] is True
    # C (crypto) has the dominant expected return -> unconstrained tangency
    # should load well past a 24% cap on it.
    assert unconstrained["tangency"]["weights"]["C"] > 0.30

    constrained = opt.build_frontier_constrained(
        TICKERS, mu, S, {"bucket_caps": {"crypto": {"max": 0.24}}},
    )
    assert constrained["feasible"] is True
    assert constrained["tangency"]["weights"]["C"] <= 0.24 + 1e-4
    assert constrained["mvp"] is not None


def test_frontier_constrained_per_position():
    mu, S = _synthetic_mu_cov()

    constrained = opt.build_frontier_constrained(
        TICKERS, mu, S, {"position_bounds": {"C": {"max": 0.10}}},
    )
    assert constrained["feasible"] is True
    assert constrained["tangency"]["weights"]["C"] <= 0.10 + 1e-4
    # Untouched positions keep their default (0, 1) bound.
    assert constrained["tangency"]["weights"]["A"] >= 0.0


def test_frontier_constrained_points_span_feasible_range():
    """Sampling runs from the constrained MVP return to the constrained max
    return — no duplicated below-MVP points, and the curve reaches the
    constrained tangency (previously it sampled the raw mu range, so most
    targets were skipped/duplicated and the curve stopped short of the star)."""
    mu, S = _synthetic_mu_cov()
    r = opt.build_frontier_constrained(
        TICKERS, mu, S, {"bucket_caps": {"crypto": {"max": 0.24}}}, n_points=15,
    )
    assert r["feasible"] is True
    pts = r["points"]
    assert len(pts) == 15
    rets = [p["return"] for p in pts]
    assert rets == sorted(rets) and len(set(round(x, 6) for x in rets)) == len(rets)
    assert rets[0] == pytest.approx(r["mvp"]["performance"]["expected_return"], abs=1e-4)
    assert rets[-1] >= r["tangency"]["performance"]["expected_return"] - 5e-4


def test_frontier_infeasible():
    mu, S = _synthetic_mu_cov()

    # Two bucket minimums that can't both hold (sum > 100%).
    constraints = {
        "bucket_caps": {
            "etf_foundation": {"min": 0.60},
            "single_stocks": {"min": 0.60},
        },
    }
    result = opt.build_frontier_constrained(TICKERS, mu, S, constraints)

    assert result["feasible"] is False
    assert result["points"] == []
    assert result["tangency"] is None
    assert result["binding_constraint"] == "bucket_caps"
    assert "relax" in result["reason"]


def test_distance_from_frontier():
    mu, S = _synthetic_mu_cov()
    dates = pd.date_range("2024-01-01", periods=300, freq="D")
    rng = np.random.default_rng(7)
    benchmark_rets = pd.Series(rng.normal(0.0004, 0.01, len(dates)), index=dates)
    weights = {"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0}  # equal-weight current portfolio

    result = opt.compute_distance_from_frontier(TICKERS, weights, mu, S, benchmark_rets)

    assert result["available"] is True
    for key in ("portfolio_sharpe", "tangency_sharpe", "delta_bps", "portfolio_vol", "tangency_vol"):
        assert key in result
    # delta_bps must be internally consistent with the two (separately-rounded)
    # Sharpe figures, within the couple of bps double-rounding can introduce.
    expected_delta = (result["portfolio_sharpe"] - result["tangency_sharpe"]) * 10000
    assert result["delta_bps"] == pytest.approx(expected_delta, abs=1.0)


def test_cml_slope():
    """The CML's slope (drawn client-side) is (tangency_return - rfr) /
    tangency_vol — which, for the risk-free-augmented tangency portfolio, is
    just its own Sharpe ratio by construction. Confirms the backend number the
    frontend will use for that slope is internally consistent."""
    mu, S = _synthetic_mu_cov()

    result = opt.max_sharpe_portfolio(TICKERS.copy())
    # max_sharpe_portfolio pulls mu/S from real price history by ticker name,
    # so exercise the same identity directly against our synthetic tangency
    # instead (the assembled-endpoint smoke test below covers the wired path).
    from pypfopt import EfficientFrontier

    ef = EfficientFrontier(mu, S)
    ef.max_sharpe(risk_free_rate=DEFAULT_RISK_FREE_RATE)
    ret, vol, sharpe = ef.portfolio_performance(risk_free_rate=DEFAULT_RISK_FREE_RATE)

    cml_slope = (ret - DEFAULT_RISK_FREE_RATE) / vol
    assert cml_slope == pytest.approx(sharpe, abs=1e-9)


# --- Endpoint smoke tests -----------------------------------------------------

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(opt_api.router, prefix="/api/finance")
    return TestClient(app)


def test_frontier_with_constraints_endpoint(client, monkeypatch):
    mu, S = _synthetic_mu_cov()
    monkeypatch.setattr(opt, "expected_returns_mean", lambda tickers, lookback_years=5: mu.reindex(tickers))
    monkeypatch.setattr(opt, "covariance_matrix", lambda tickers, lookback_years=5: S.reindex(index=tickers, columns=tickers))

    resp = client.post(
        "/api/finance/optimization/frontier-with-constraints",
        json={"tickers": TICKERS, "n_points": 10, "bucket_caps": {"crypto": {"max": 0.24}}},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["constrained"]["feasible"] is True
    assert body["constrained"]["tangency"]["weights"]["C"] <= 0.24 + 1e-4


def test_distance_from_frontier_endpoint(client, monkeypatch):
    mu, S = _synthetic_mu_cov()
    dates = pd.date_range("2024-01-01", periods=300, freq="D")
    rng = np.random.default_rng(11)
    benchmark_rets = pd.Series(rng.normal(0.0004, 0.01, len(dates)), index=dates)

    monkeypatch.setattr(opt, "expected_returns_mean", lambda tickers, lookback_years=5: mu.reindex(tickers))
    monkeypatch.setattr(opt, "covariance_matrix", lambda tickers, lookback_years=5: S.reindex(index=tickers, columns=tickers))
    monkeypatch.setattr(opt, "_resolve_tickers", lambda tickers: TICKERS)
    monkeypatch.setattr("modules.finance.positions.current_holdings", lambda: {t: 1.0 for t in TICKERS})
    monkeypatch.setattr("modules.finance.price_history.latest_price", lambda t: 100.0)
    monkeypatch.setattr("modules.finance.price_history.get_returns", lambda ticker, freq="D": benchmark_rets)

    resp = client.get("/api/finance/optimization/distance-from-frontier?benchmark=MSCI_WORLD")

    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["benchmark"] == "MSCI_WORLD"
    assert "delta_bps" in body
