"""Tests for modules/finance/capm_view.py and the /performance/sml + /capm-decomposition
endpoints (Chunk 6, D3/D4). Synthetic returns with known betas/alphas; network-free.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import performance as perf_api
from core.config import BENCHMARKS, DEFAULT_RISK_FREE_RATE
from modules.finance import capm_view as cv
from modules.finance import optimization as opt

N = 900
DATES = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=N)
TICKERS = ["HI", "MID", "LOW", "LAG"]
TRUE = {  # ticker -> (beta, daily alpha)
    "HI": (1.6, 0.0006),    # high beta, strong positive alpha
    "MID": (1.0, 0.0),
    "LOW": (0.5, 0.0),
    "LAG": (1.2, -0.0006),  # negative alpha
}
WEIGHTS = {"HI": 0.4, "MID": 0.3, "LOW": 0.2, "LAG": 0.1}


def _market(seed, mean, vol):
    return pd.Series(np.random.default_rng(seed).normal(mean, vol, N), index=DATES)


@pytest.fixture
def world(monkeypatch):
    """Assets are generated off URTH (MSCI World); ^GSPC is an independent series."""
    urth = _market(1, 0.0006, 0.010)
    gspc = _market(2, 0.0003, 0.014)
    rng = np.random.default_rng(7)
    series = {t: a + b * urth + pd.Series(rng.normal(0, 0.004, N), index=DATES) for t, (b, a) in TRUE.items()}
    series.update({BENCHMARKS["MSCI_WORLD"]["ticker"]: urth, BENCHMARKS["SPY"]["ticker"]: gspc})

    fetch = lambda ticker, freq="D": series.get(ticker, pd.Series(dtype="float64"))  # noqa: E731
    monkeypatch.setattr(cv, "get_returns", fetch)
    monkeypatch.setattr(opt, "get_returns", fetch)  # get_returns_matrix reads this name
    monkeypatch.setattr(cv, "current_holdings", lambda: {t: 1.0 for t in TICKERS})
    monkeypatch.setattr(cv, "_weights", lambda tickers: {t: w for t, w in WEIGHTS.items() if t in tickers})
    return series


# --- Security Market Line ----------------------------------------------------------------

def test_sml_line_and_points(world):
    sml = cv.security_market_line("MSCI_WORLD")

    assert sml["available"] is True
    rf = DEFAULT_RISK_FREE_RATE
    market_mean = float(world["URTH"].mean() * 252)
    assert sml["line"]["intercept"] == rf
    assert sml["line"]["slope"] == pytest.approx(market_mean - rf, rel=0.05)  # 5y-window vs full-sample mean
    assert sml["market"]["beta"] == 1.0

    pts = {p["ticker"]: p for p in sml["points"]}
    assert set(pts) == set(TICKERS)
    for t, (beta, _) in TRUE.items():
        assert pts[t]["beta"] == pytest.approx(beta, abs=0.08)
        # y on the line is rf + beta * slope, and alpha is the gap to actual.
        assert pts[t]["expected_return_capm"] == pytest.approx(rf + pts[t]["beta"] * sml["line"]["slope"])
        assert pts[t]["alpha"] == pytest.approx(pts[t]["actual_return"] - pts[t]["expected_return_capm"])


def test_sml_alpha_sign_puts_points_above_and_below_the_line(world):
    pts = {p["ticker"]: p for p in cv.security_market_line("MSCI_WORLD")["points"]}

    assert pts["HI"]["alpha"] > 0.05   # +0.0006/day * 252 ~ +15%/yr above the line
    assert pts["LAG"]["alpha"] < -0.05  # below the line
    assert abs(pts["MID"]["alpha"]) < 0.05


def test_sml_uses_the_same_capm_expected_returns_as_the_optimizer(world):
    """The chunk's core promise: SML expected returns == Optimization tab mu."""
    sml = {p["ticker"]: p for p in cv.security_market_line("MSCI_WORLD")["points"]}
    mu, _ = opt.mu_cov(TICKERS, BENCHMARKS["MSCI_WORLD"]["ticker"])

    for t in TICKERS:
        assert sml[t]["expected_return_capm"] == pytest.approx(mu[t], rel=1e-9)


def test_sml_portfolio_roll_up_is_weighted(world):
    sml = cv.security_market_line("MSCI_WORLD")
    pts = {p["ticker"]: p for p in sml["points"]}

    for key in ("beta", "expected_return_capm", "actual_return", "alpha"):
        assert sml["portfolio"][key] == pytest.approx(sum(WEIGHTS[t] * pts[t][key] for t in TICKERS))


def test_sml_reshapes_with_benchmark(world):
    a = cv.security_market_line("MSCI_WORLD")
    b = cv.security_market_line("SPY")

    assert a["line"]["slope"] != pytest.approx(b["line"]["slope"], abs=0.01)
    pa = {p["ticker"]: p["beta"] for p in a["points"]}
    pb = {p["ticker"]: p["beta"] for p in b["points"]}
    assert pa["HI"] != pytest.approx(pb["HI"], abs=0.2)  # HI is built off MSCI, not the S&P


def test_sml_with_no_holdings_still_returns_the_line(world, monkeypatch):
    monkeypatch.setattr(cv, "current_holdings", lambda: {})
    sml = cv.security_market_line("MSCI_WORLD")

    assert sml["available"] is True and sml["points"] == [] and sml["portfolio"] is None
    assert sml["line"]["intercept"] == DEFAULT_RISK_FREE_RATE and sml["reason"] == "no holdings"


def test_sml_without_benchmark_data(monkeypatch):
    monkeypatch.setattr(cv, "get_returns", lambda t, freq="D": pd.Series(dtype="float64"))
    out = cv.security_market_line("MSCI_WORLD", tickers=["X"])
    assert out["available"] is False and out["points"] == [] and out["line"] is None


# --- Return decomposition -----------------------------------------------------------------

def test_decomposition_sums_to_actual_return(world):
    for period in ("1m", "6m", "ytd", "1y", "3y", "all"):
        d = cv.capm_return_decomposition("MSCI_WORLD", period)
        assert d["available"] is True, period
        for r in [*d["rows"], d["portfolio"]]:
            assert r["market"] + r["alpha"] + r["idiosyncratic"] == pytest.approx(r["actual_return"], abs=1e-12)


def test_decomposition_components(world):
    d = cv.capm_return_decomposition("MSCI_WORLD", "1y")
    rows = {r["ticker"]: r for r in d["rows"]}
    reg, _ = opt.capm_regression(opt.get_returns_matrix(TICKERS, 5), world["URTH"])

    assert d["days"] > 240 and d["market_return"] is not None
    for t in TICKERS:
        assert rows[t]["market"] == pytest.approx(rows[t]["beta"] * d["market_return"])  # beta x Rm
        assert rows[t]["alpha"] == pytest.approx(reg.loc[t, "alpha_daily"] * d["days"])  # intercept x days
    assert rows["HI"]["alpha"] > 0 > rows["LAG"]["alpha"]
    assert d["portfolio"]["beta"] == pytest.approx(sum(WEIGHTS[t] * rows[t]["beta"] for t in TICKERS))  # weighted roll-up
    assert rows["HI"]["beta"] > rows["MID"]["beta"] > rows["LOW"]["beta"]  # betas recovered in the right order


def test_decomposition_period_and_benchmark_change_the_numbers(world):
    one, three = cv.capm_return_decomposition("MSCI_WORLD", "1y"), cv.capm_return_decomposition("MSCI_WORLD", "3y")
    spy = cv.capm_return_decomposition("SPY", "1y")

    assert one["portfolio"]["actual_return"] != pytest.approx(three["portfolio"]["actual_return"], abs=1e-3)
    assert one["market_return"] != pytest.approx(spy["market_return"], abs=1e-3)
    assert one["rows"][0]["beta"] != pytest.approx(spy["rows"][0]["beta"], abs=0.05)
    assert cv.capm_return_decomposition("MSCI_WORLD", "1Y")["period"] == "1y"  # case-insensitive


def test_decomposition_empty_ledger(world, monkeypatch):
    monkeypatch.setattr(cv, "current_holdings", lambda: {})
    d = cv.capm_return_decomposition("MSCI_WORLD", "1y")
    assert d["available"] is False and d["rows"] == [] and d["reason"] == "no holdings to decompose"


# --- endpoints -------------------------------------------------------------------------------

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(perf_api.router, prefix="/api/finance")
    return TestClient(app)


def test_sml_endpoint(client, world):
    body = client.get("/api/finance/performance/sml?benchmark=SPY").json()
    assert body["benchmark"] == "SPY" and body["available"] and len(body["points"]) == 4
    assert client.get("/api/finance/performance/sml").json()["benchmark"] == "MSCI_WORLD"


def test_decomposition_endpoint(client, world):
    body = client.get("/api/finance/performance/capm-decomposition?benchmark=MSCI_WORLD&period=1Y").json()
    assert body["period"] == "1y" and len(body["rows"]) == 4 and body["portfolio"]["ticker"] == "portfolio"
    assert client.get("/api/finance/performance/capm-decomposition?period=5y").status_code == 422
