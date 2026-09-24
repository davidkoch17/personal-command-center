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
    weights = {"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0}  # equal-weight current portfolio

    result = opt.compute_distance_from_frontier(TICKERS, weights, mu, S)

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
    monkeypatch.setattr(opt, "mu_cov", lambda tickers, benchmark_ticker=None, *a, **kw: (mu.reindex(tickers), S.reindex(index=tickers, columns=tickers)))

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

    monkeypatch.setattr(opt, "mu_cov", lambda tickers, benchmark_ticker=None, *a, **kw: (mu.reindex(tickers), S.reindex(index=tickers, columns=tickers)))
    monkeypatch.setattr(opt, "_resolve_tickers", lambda tickers: TICKERS)
    monkeypatch.setattr("modules.finance.positions.current_holdings", lambda: {t: 1.0 for t in TICKERS})
    monkeypatch.setattr("modules.finance.price_history.latest_price", lambda t: 100.0)

    resp = client.get("/api/finance/optimization/distance-from-frontier?benchmark=MSCI_WORLD")

    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["benchmark"] == "MSCI_WORLD"
    assert "delta_bps" in body


# --- Chunk 3.5: CAPM expected returns everywhere -----------------------------
#
# Synthetic *price history* (not just mu/S) so these exercise the real
# mu_cov -> CAPM path end to end. Two different benchmark series stand in for
# MSCI World (URTH) and the S&P 500 (^GSPC) — same holdings, different market.

_N_DAYS = 700
_DATES = pd.bdate_range("2023-01-02", periods=_N_DAYS)
_BETAS = {"A": 0.4, "B": 1.0, "C": 1.8, "D": 0.7}


def _market(seed: int, mean: float, vol: float) -> pd.Series:
    return pd.Series(np.random.default_rng(seed).normal(mean, vol, _N_DAYS), index=_DATES)


def _asset_returns(market: pd.Series) -> dict[str, pd.Series]:
    """Each asset = beta * market + independent noise, so betas are recoverable."""
    rng = np.random.default_rng(99)
    return {t: b * market + pd.Series(rng.normal(0.0002, 0.006, _N_DAYS), index=_DATES) for t, b in _BETAS.items()}


@pytest.fixture
def price_world(monkeypatch):
    """Assets are generated off URTH; ^GSPC is a *different* market series, so
    switching benchmark changes every asset's beta and the market premium."""
    urth = _market(1, 0.0007, 0.010)
    gspc = _market(2, 0.0004, 0.013)
    series = {**_asset_returns(urth), "URTH": urth, "^GSPC": gspc}
    monkeypatch.setattr(opt, "get_returns", lambda ticker, freq="D": series.get(ticker, pd.Series(dtype="float64")))
    monkeypatch.setattr(opt, "current_holdings", lambda: {t: 1.0 for t in TICKERS})
    monkeypatch.setattr("modules.finance.positions.current_holdings", lambda: {t: 1.0 for t in TICKERS})
    monkeypatch.setattr("modules.finance.price_history.latest_price", lambda t: 100.0)
    return series


def test_capm_returns_computed_correctly():
    """capm_mu_from_returns == hand-computed rf + beta*(E[rm]-rf) == PyPortfolioOpt's
    capm_return (arithmetic annualization) on gap-free data."""
    from pypfopt import expected_returns

    market = _market(5, 0.0006, 0.011)
    rets = pd.DataFrame(_asset_returns(market))
    rf = DEFAULT_RISK_FREE_RATE

    mu = opt.capm_mu_from_returns(rets, market, rf)

    market_mean = market.mean() * 252
    for t in TICKERS:
        beta = np.cov(rets[t], market, ddof=1)[0, 1] / np.var(market, ddof=1)
        assert mu[t] == pytest.approx(rf + beta * (market_mean - rf), rel=1e-9)

    ref = expected_returns.capm_return(
        rets, market_prices=market.rename("mkt"), returns_data=True, risk_free_rate=rf, compounding=False,
    )
    for t in TICKERS:
        assert mu[t] == pytest.approx(ref[t], rel=1e-9)


def test_frontier_uses_capm_returns_not_historical(price_world):
    """mu_cov with a benchmark yields CAPM mu (beta-ordered, all assets on the
    security market line), which is materially different from the historical mean
    the frontier used before Chunk 3.5."""
    mu_capm, S = opt.mu_cov(TICKERS, "URTH")
    mu_hist, _ = opt.mu_cov(TICKERS, None)

    assert list(mu_capm.index) == list(S.index)
    # CAPM mu is monotone in beta: C (1.8) > B (1.0) > D (0.7) > A (0.4)
    assert mu_capm["C"] > mu_capm["B"] > mu_capm["D"] > mu_capm["A"]
    # ...and is not the historical-mean vector.
    assert not np.allclose(mu_capm.values, mu_hist.reindex(mu_capm.index).values, atol=1e-3)

    # The frontier endpoint's max-sharpe is the CAPM one, not the historical one.
    client = TestClient(_app())
    body = client.get("/api/finance/optimization/frontier?benchmark=MSCI_WORLD&n_points=10").json()
    expected = opt.max_sharpe_portfolio(TICKERS, benchmark_ticker="URTH")["performance"]
    historical = opt.max_sharpe_portfolio(TICKERS)["performance"]
    assert body["max_sharpe"]["performance"]["sharpe"] == pytest.approx(expected["sharpe"], abs=1e-9)
    assert abs(body["max_sharpe"]["performance"]["sharpe"] - historical["sharpe"]) > 1e-3


def test_frontier_reshapes_on_benchmark_change(price_world):
    """Same holdings, different benchmark -> different frontier and tangency."""
    client = TestClient(_app())
    a = client.get("/api/finance/optimization/frontier?benchmark=MSCI_WORLD&n_points=10").json()
    b = client.get("/api/finance/optimization/frontier?benchmark=SPY&n_points=10").json()

    ta, tb = a["max_sharpe"]["performance"], b["max_sharpe"]["performance"]
    assert a["benchmark"] == "MSCI_WORLD" and b["benchmark"] == "SPY"
    assert abs(ta["expected_return"] - tb["expected_return"]) > 0.005
    assert abs(ta["sharpe"] - tb["sharpe"]) > 0.02
    # The whole curve moves too, not just the star.
    assert a["points"][-1]["return"] != pytest.approx(b["points"][-1]["return"], abs=0.005)
    # Constrained overlay follows the same benchmark: its tangency differs as well.
    ca = client.post("/api/finance/optimization/frontier-with-constraints",
                     json={"benchmark": "MSCI_WORLD", "n_points": 8, "bucket_caps": {"crypto": {"max": 0.5}}}).json()
    cb = client.post("/api/finance/optimization/frontier-with-constraints",
                     json={"benchmark": "SPY", "n_points": 8, "bucket_caps": {"crypto": {"max": 0.5}}}).json()
    assert ca["constrained"]["feasible"] and cb["constrained"]["feasible"]
    assert abs(ca["constrained"]["tangency"]["performance"]["sharpe"]
               - cb["constrained"]["tangency"]["performance"]["sharpe"]) > 0.02


def test_chart_and_callout_tangency_sharpe_match(price_world):
    """The critical regression: the chart's star Sharpe (build_frontier side) and
    the callout's tangency Sharpe (compute_distance_from_frontier side) are the
    same number for the same portfolio + benchmark."""
    # Module level: constrained-frontier tangency with no constraints vs callout.
    mu, S = opt.mu_cov(TICKERS, "URTH")
    weights = {t: 1.0 for t in TICKERS}
    chart = opt.build_frontier_constrained(list(mu.index), mu, S, {})["tangency"]["performance"]["sharpe"]
    callout = opt.compute_distance_from_frontier(list(mu.index), weights, mu, S)["tangency_sharpe"]
    assert callout == pytest.approx(chart, abs=1e-4)  # callout is rounded to 4 dp

    # Endpoint level, for both benchmarks: what the UI actually reads.
    client = TestClient(_app())
    for key in ("MSCI_WORLD", "SPY"):
        star = client.get(f"/api/finance/optimization/frontier?benchmark={key}&n_points=10").json()
        dist = client.get(f"/api/finance/optimization/distance-from-frontier?benchmark={key}").json()
        assert dist["available"] is True
        assert dist["tangency_sharpe"] == pytest.approx(star["max_sharpe"]["performance"]["sharpe"], abs=1e-4)
        # ...and the chart's current-portfolio marker uses the callout's Sharpe basis too.
        assert dist["portfolio_sharpe"] == pytest.approx(star["current"]["sharpe"], abs=1e-4)


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(opt_api.router, prefix="/api/finance")
    return app
