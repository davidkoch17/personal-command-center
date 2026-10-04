"""The risk-free rate is a shared UI setting (Chunk 8): every endpoint that computes a Sharpe /
Sortino / CAPM figure takes ``rfr`` (or ``rfr`` in the body), defaults to the hardcoded 4% when
omitted, passes a supplied value straight through, and rejects nonsense.

The compute layers are monkeypatched to *record* the rate they were called with, so this tests the
plumbing (endpoint -> module) without any market data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import benchmarks as bench_api
from backend.api.finance import dashboard as dash_api
from backend.api.finance import forward_whatif as fw_api
from backend.api.finance import optimization as opt_api
from backend.api.finance import performance as perf_api
from core.config import BENCHMARKS, DEFAULT_RISK_FREE_RATE
from modules.finance import benchmarks as bm
from modules.finance import capm_view, dashboard, forward_whatif as fw, optimization as opt


def _client(*routers):
    app = FastAPI()
    for r in routers:
        app.include_router(r, prefix="/api/finance")
    return TestClient(app)


def test_the_default_is_four_percent():
    assert DEFAULT_RISK_FREE_RATE == 0.04


# --- optimization ---------------------------------------------------------------------------------------

@pytest.fixture
def opt_calls(monkeypatch):
    calls: dict[str, float] = {}
    monkeypatch.setattr(opt, "_resolve_tickers", lambda t: ["A"])

    def rec(name, ret):
        def f(*a, **k):
            calls[name] = k.get("risk_free", a[1] if name == "max_sharpe" and len(a) > 1 else None)
            return ret
        return f

    monkeypatch.setattr(opt, "efficient_frontier_points", rec("points", []))
    monkeypatch.setattr(opt, "max_sharpe_portfolio", rec("max_sharpe", {"weights": {}, "performance": None}))
    monkeypatch.setattr(opt, "min_variance_portfolio", rec("min_var", {"weights": {}, "performance": None}))
    monkeypatch.setattr(opt, "current_portfolio_point", rec("current", None))
    return calls


def test_frontier_defaults_to_four_percent_and_passes_a_supplied_rate(opt_calls):
    client = _client(opt_api.router)

    body = client.get("/api/finance/optimization/frontier").json()
    assert body["risk_free_rate"] == 0.04
    assert opt_calls == {"points": 0.04, "max_sharpe": 0.04, "min_var": 0.04, "current": 0.04}

    body = client.get("/api/finance/optimization/frontier?rfr=0.065").json()
    assert body["risk_free_rate"] == 0.065  # the CML's intercept follows the setting
    assert set(opt_calls.values()) == {0.065}


def test_frontier_rejects_an_absurd_rate(opt_calls):
    client = _client(opt_api.router)
    assert client.get("/api/finance/optimization/frontier?rfr=0.9").status_code == 422
    assert client.get("/api/finance/optimization/frontier?rfr=-0.01").status_code == 422


def test_constrained_frontier_and_distance_take_the_rate(monkeypatch):
    seen = {}
    monkeypatch.setattr(opt, "_resolve_tickers", lambda t: ["A"])
    monkeypatch.setattr(opt, "mu_cov", lambda tk, bt=None, rf=None, *a, **k: seen.setdefault("mu_cov", []).append(rf) or (pd.Series(dtype="float64"), pd.DataFrame()))
    monkeypatch.setattr(opt, "build_frontier_constrained", lambda *a, **k: seen.setdefault("frontier_rf", k.get("risk_free")) and {"feasible": False})
    monkeypatch.setattr(opt, "compute_distance_from_frontier", lambda tk, w, mu, S, rf=None: seen.setdefault("distance_rf", rf) and {"available": False})
    monkeypatch.setattr("modules.finance.positions.current_holdings", lambda: {})
    client = _client(opt_api.router)

    client.post("/api/finance/optimization/frontier-with-constraints", json={"rfr": 0.07})
    client.post("/api/finance/optimization/frontier-with-constraints", json={})
    client.get("/api/finance/optimization/distance-from-frontier?rfr=0.07")

    assert seen["mu_cov"] == [0.07, 0.04, 0.07] and seen["frontier_rf"] == 0.07 and seen["distance_rf"] == 0.07


# --- SML, benchmarks, forward what-if, dashboard --------------------------------------------------------------

def test_sml_endpoint_rate(monkeypatch):
    seen = []
    monkeypatch.setattr(capm_view, "security_market_line", lambda benchmark="X", tickers=None, risk_free=None: seen.append(risk_free) or {"ok": True})
    client = _client(perf_api.router)
    client.get("/api/finance/performance/sml")
    client.get("/api/finance/performance/sml?rfr=0.03")
    assert seen == [0.04, 0.03]


def test_benchmarks_compare_reports_and_applies_the_rate(monkeypatch):
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=400)
    rng = np.random.default_rng(1)
    series = {b["ticker"]: pd.Series(100 * np.cumprod(1 + rng.normal(0.0004, 0.01, 400)), index=idx) for b in BENCHMARKS.values()}
    monkeypatch.setattr(bm, "get_closes", lambda t: series[t])
    client = _client(bench_api.router)

    default = client.get("/api/finance/benchmarks/compare?period=1y").json()
    high = client.get("/api/finance/benchmarks/compare?period=1y&rfr=0.10").json()

    assert default["risk_free_rate"] == 0.04 and high["risk_free_rate"] == 0.10
    for key in ("MSCI_WORLD", "SPY", "DAX", "STOXX_600"):
        assert high["metrics"][key]["sharpe"] < default["metrics"][key]["sharpe"]
        assert high["metrics"][key]["return"] == default["metrics"][key]["return"]  # only Sharpe moves


def test_forward_whatif_takes_the_rate_in_the_body(monkeypatch):
    seen = []
    monkeypatch.setattr(fw, "simulate_forward_trade", lambda t, a, e, b="X", rf=None: seen.append(rf) or {"ok": True})
    client = _client(fw_api.router)
    client.post("/api/finance/scenarios/forward-whatif", json={"ticker": "A", "action": "buy", "eur_amount": 1})
    client.post("/api/finance/scenarios/forward-whatif", json={"ticker": "A", "action": "buy", "eur_amount": 1, "rfr": 0.02})
    assert seen == [0.04, 0.02]


def test_forward_whatif_sharpe_uses_the_rate(monkeypatch):
    idx = pd.bdate_range("2024-01-01", periods=300)
    rets = pd.Series(np.random.default_rng(3).normal(0.0006, 0.01, len(idx)), index=idx)
    monkeypatch.setattr(fw, "portfolio_returns", lambda h: rets)
    monkeypatch.setattr(fw, "mu_cov", lambda t, b=None, rf=0.04, *a, **k: (pd.Series({"A": 0.06 + rf}), pd.DataFrame([[0.04]], index=["A"], columns=["A"])))
    lo = fw._risk_metrics({"A": 1.0}, {"A": 1.0}, "URTH", 0.0)
    hi = fw._risk_metrics({"A": 1.0}, {"A": 1.0}, "URTH", 0.08)
    assert hi["sharpe_historical"] < lo["sharpe_historical"] and hi["sortino"] < lo["sortino"]
    assert fw._risk_metrics({"A": 1.0}, {"A": 1.0}, "URTH")["sharpe_historical"] == pytest.approx(
        fw._risk_metrics({"A": 1.0}, {"A": 1.0}, "URTH", 0.04)["sharpe_historical"])  # omitted -> 4%


def test_black_litterman_takes_the_rate_in_the_body(monkeypatch):
    """Chunk 9 — the Chunk 8 leftover: BL's CAPM prior + posterior Sharpe both take ``rfr``."""
    seen = []
    monkeypatch.setattr(opt, "_resolve_tickers", lambda t: ["A"])
    monkeypatch.setattr(opt, "hypotheses_as_views", lambda: [])
    monkeypatch.setattr(
        opt, "black_litterman_with_hypotheses",
        lambda tk, market_caps=None, views=None, risk_aversion=2.5, risk_free=None:
            seen.append(risk_free) or {"weights": {}, "performance": None, "views_used": []},
    )
    client = _client(opt_api.router)
    client.post("/api/finance/optimization/black-litterman", json={})
    client.post("/api/finance/optimization/black-litterman", json={"rfr": 0.08})
    assert seen == [0.04, 0.08]


def test_dashboard_summary_rate(monkeypatch):
    seen = []
    monkeypatch.setattr(dashboard, "summary", lambda benchmark="X", risk_free=None: seen.append(risk_free) or {"ok": True})
    client = _client(dash_api.router)
    client.get("/api/finance/dashboard/summary")
    client.get("/api/finance/dashboard/summary?rfr=0.05")
    assert seen == [0.04, 0.05]
