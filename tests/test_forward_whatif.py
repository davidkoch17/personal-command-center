"""Tests for modules/finance/forward_whatif.py and POST /scenarios/forward-whatif (Chunk 7, D5).

A synthetic 10,000-unit portfolio; every data seam (holdings, prices, FX, bucket map,
risk inputs) is monkeypatched so nothing touches the network, the ledger or the cache.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import forward_whatif as fw_api
from core.config import BENCHMARKS, DEFAULT_RISK_FREE_RATE
from modules.finance import forward_whatif as fw

# ticker -> (bucket, source, type, price, qty).  Portfolio = 10,000: ETF 50%, stocks 30%, crypto 20%.
WORLD = {
    "VWCE.DE": ("etf_foundation", "map", "etf", 100.0, 50),
    "ADBE": ("single_stocks", "map", "equity", 100.0, 30),
    "BTC-USD": ("crypto", "map", "crypto", 100.0, 20),
}
EXTRA_BUCKETS = {"NEWCO": ("single_stocks", "map"), "COIN2": ("crypto", "map"), "MYSTERY": ("unassigned", "unassigned")}
EXTRA_PRICES = {"NEWCO": 50.0, "COIN2": 10.0, "MYSTERY": 20.0}


@pytest.fixture
def world(monkeypatch):
    holdings = {t: v[4] for t, v in WORLD.items()}
    prices = {t: v[3] for t, v in WORLD.items()} | EXTRA_PRICES

    def bucket_of(t):
        if t in WORLD:
            return WORLD[t][0], WORLD[t][1]
        return EXTRA_BUCKETS.get(t, ("unassigned", "unassigned"))

    monkeypatch.setattr(fw, "current_holdings", lambda: dict(holdings))
    monkeypatch.setattr(fw, "latest_price", lambda t: prices.get(t))
    monkeypatch.setattr(fw, "native_to_eur", lambda t: (1.0, False))
    monkeypatch.setattr(fw, "resolve_bucket_with_source", bucket_of)
    monkeypatch.setattr(fw, "get_position", lambda t: SimpleNamespace(type=WORLD[t][2]) if t in WORLD else None)
    # default risk numbers: a function of the holdings so deltas are non-trivial
    monkeypatch.setattr(fw, "_risk_metrics", lambda h, p, b: {
        "sharpe_capm": 0.5 + 0.01 * len(h), "sharpe_historical": 1.0 - 0.001 * sum(h.values()),
        "sortino": 1.5, "vol": 0.10 + 0.001 * len(h),
    })
    return holdings


def _row(res, bucket):
    return next(r for r in res["bucket_table"] if r["bucket"] == bucket)


# --- bucket assignment on buy ---------------------------------------------------------------

def test_buy_maps_the_ticker_to_its_bucket_via_resolve_bucket(world):
    res = fw.simulate_forward_trade("newco", "buy", 1000)

    assert res["ticker"] == "NEWCO" and res["action"] == "buy"
    assert res["bucket"] == {"bucket": "single_stocks", "label": "Single Stocks", "source": "map"}
    assert res["units"] == pytest.approx(20.0)  # 1000 EUR / 50


def test_unassigned_ticker_is_analysed_as_single_stocks_with_a_warning(world):
    res = fw.simulate_forward_trade("MYSTERY", "buy", 1000)

    assert res["bucket"]["bucket"] == "unassigned"
    assert _row(res, "single_stocks")["projected_value"] == pytest.approx(3000 + 1000)
    assert any("no bucket yet" in w for w in res["warnings"])


# --- drift / allocation calc ------------------------------------------------------------------

def test_projected_allocation_and_drift_delta(world):
    res = fw.simulate_forward_trade("ADBE", "buy", 2000)

    assert res["portfolio_value"] == {"current": 10000, "projected": 12000}
    stocks = _row(res, "single_stocks")
    assert stocks["current_weight"] == pytest.approx(0.30) and stocks["projected_weight"] == pytest.approx(5000 / 12000)
    assert stocks["weight_delta"] == pytest.approx(5000 / 12000 - 0.30)
    assert stocks["current_drift"] == pytest.approx(0.30 - 0.21)
    assert stocks["drift_delta"] == pytest.approx(stocks["projected_drift"] - stocks["current_drift"])
    assert sum(r["projected_weight"] for r in res["bucket_table"]) == pytest.approx(1.0)
    assert res["projected_holdings"]["ADBE"] == pytest.approx(50.0)


def test_eur_amount_converts_to_units_at_the_tickers_fx_rate(world, monkeypatch):
    monkeypatch.setattr(fw, "native_to_eur", lambda t: (0.5, False))  # USD-ish: 100 native = 50 EUR
    res = fw.simulate_forward_trade("ADBE", "buy", 2000)

    assert res["price_eur"] == pytest.approx(50.0) and res["units"] == pytest.approx(40.0)


def test_fx_failure_is_flagged_not_fatal(world, monkeypatch):
    monkeypatch.setattr(fw, "native_to_eur", lambda t: (1.0, True))
    res = fw.simulate_forward_trade("ADBE", "buy", 500)
    assert res["fx_assumed"] is True and any("EUR conversion" in w for w in res["warnings"])


# --- cap / concentration breach detection --------------------------------------------------------

def test_buy_that_breaches_bucket_caps_and_hard_triggers(world):
    res = fw.simulate_forward_trade("COIN2", "buy", 6000)  # crypto 2000 -> 8000 of 16000 = 50%

    crypto = next(b for b in res["bucket_band_breaches"] if b["bucket"] == "crypto")
    assert crypto["projected_weight"] == pytest.approx(0.5) and crypto["new"] is True and crypto["worsened"] is True
    assert any(h["bucket"] == "crypto" and "30%" in h["rule"] for h in res["hard_cap_breaches"])
    assert any("Crypto would be 50.0%" in w for w in res["warnings"])
    assert any("30% trigger" in w for w in res["warnings"])


def test_etf_floor_breach_when_the_core_gets_diluted(world):
    res = fw.simulate_forward_trade("NEWCO", "buy", 9000)  # ETF 5000 -> 5000/19000 = 26%
    assert any(h["bucket"] == "etf_foundation" for h in res["hard_cap_breaches"])


def test_concentration_and_position_caps_flagged_for_the_traded_ticker(world):
    res = fw.simulate_forward_trade("NEWCO", "buy", 5000)  # 5000 of 15000 = 33%

    assert [c["ticker"] for c in res["concentration_breaches"]][0] == "NEWCO"
    assert res["concentration_breaches"][0]["limit"] == 0.10
    assert any("single-position limit" in w and "NEWCO" in w for w in res["warnings"])
    assert any(a["ticker"] == "NEWCO" and a["type"] == "drift_trigger" for a in res["position_cap_alerts"])  # Section 0.2


def test_the_etf_core_is_exempt_from_the_single_position_limit(world):
    res = fw.simulate_forward_trade("NEWCO", "buy", 100)
    assert res["top1"]["ticker"] == "VWCE.DE" and res["top1"]["weight"] > 0.10   # the literal top-1 figure is reported...
    assert all(c["ticker"] != "VWCE.DE" for c in res["concentration_breaches"])   # ...but the ETF isn't flagged


def test_a_small_trade_toward_target_has_no_new_warnings(world):
    # crypto sits at -4pp; a small crypto buy moves it toward target (and stocks shrink slightly)
    res = fw.simulate_forward_trade("BTC-USD", "buy", 100)
    assert res["hard_cap_breaches"] == []
    assert not any("outside ±" in w for w in res["warnings"])  # no bucket newly outside its ±4pp band


# --- sells / errors -------------------------------------------------------------------------------

def test_sell_reduces_the_position_and_shifts_the_bucket(world):
    res = fw.simulate_forward_trade("BTC-USD", "sell", 1000)

    assert res["units"] == pytest.approx(10.0) and res["projected_holdings"]["BTC-USD"] == pytest.approx(10.0)
    assert _row(res, "crypto")["projected_weight"] == pytest.approx(1000 / 9000)


def test_selling_more_than_held_is_capped_with_a_warning_and_a_full_exit_drops_the_position(world):
    res = fw.simulate_forward_trade("BTC-USD", "sell", 5000)

    assert res["capped"] is True and res["units"] == pytest.approx(20.0) and res["eur_effective"] == pytest.approx(2000)
    assert "BTC-USD" not in res["projected_holdings"]
    assert any("capped" in w for w in res["warnings"])


def test_selling_an_unowned_ticker_is_a_clean_error(world):
    with pytest.raises(fw.WhatIfError, match="don't hold NEWCO"):
        fw.simulate_forward_trade("NEWCO", "sell", 500)


@pytest.mark.parametrize("args, msg", [
    (("ADBE", "hold", 100), "buy' or 'sell"),
    (("ADBE", "buy", 0), "positive"),
    (("ADBE", "buy", -5), "positive"),
    (("bad ticker!", "buy", 100), "valid ticker"),
    (("NOPRICE", "buy", 100), "no price data"),
])
def test_invalid_input_is_rejected_with_a_plain_message(world, args, msg):
    with pytest.raises(fw.WhatIfError, match=msg):
        fw.simulate_forward_trade(*args)


def test_empty_ledger_still_works_and_skips_bucket_band_noise(world, monkeypatch):
    monkeypatch.setattr(fw, "current_holdings", lambda: {})
    res = fw.simulate_forward_trade("NEWCO", "buy", 5000)

    assert res["portfolio_value"] == {"current": 0, "projected": 5000}
    assert res["bucket_band_breaches"] == [] and res["hard_cap_breaches"] == []  # any first buy breaches every band
    assert any("portfolio is empty" in w for w in res["warnings"])
    assert res["concentration_breaches"][0]["weight"] == pytest.approx(1.0)      # ...but 100% in one name is real


# --- risk metrics -----------------------------------------------------------------------------------

def test_metric_deltas_are_projected_minus_current(world):
    res = fw.simulate_forward_trade("NEWCO", "buy", 1000)
    for key in ("sharpe_capm", "sharpe_historical", "sortino", "vol"):
        m = res["metrics"][key]
        assert m["delta"] == pytest.approx(m["projected"] - m["current"]), key
    assert res["metrics"]["vol"]["projected"] > res["metrics"]["vol"]["current"]  # one more holding in the stub


def _real_risk_env(monkeypatch, mu_by_benchmark):
    """Wire the *real* _risk_metrics to synthetic returns and a per-benchmark mu."""
    idx = pd.bdate_range("2024-01-01", periods=300)
    rng = np.random.default_rng(3)
    rets = pd.Series(rng.normal(0.0005, 0.01, len(idx)), index=idx)
    seen = []
    S = pd.DataFrame(np.diag([0.04, 0.09]), index=["A", "B"], columns=["A", "B"])

    def fake_mu_cov(tickers, benchmark_ticker=None, *a, **k):
        seen.append(benchmark_ticker)
        return mu_by_benchmark[benchmark_ticker].reindex(tickers), S.reindex(index=tickers, columns=tickers)

    monkeypatch.setattr(fw, "portfolio_returns", lambda holdings: rets)
    monkeypatch.setattr(fw, "mu_cov", fake_mu_cov)
    return rets, S, seen


def test_capm_sharpe_uses_the_selected_benchmarks_mu(monkeypatch):
    urth, spx = BENCHMARKS["MSCI_WORLD"]["ticker"], BENCHMARKS["SPY"]["ticker"]
    mus = {urth: pd.Series({"A": 0.10, "B": 0.20}), spx: pd.Series({"A": 0.06, "B": 0.08})}
    _, S, seen = _real_risk_env(monkeypatch, mus)
    holdings, prices = {"A": 10.0, "B": 10.0}, {"A": 100.0, "B": 100.0}

    a = fw._risk_metrics(holdings, prices, urth)
    b = fw._risk_metrics(holdings, prices, spx)

    w = np.array([0.5, 0.5])
    expected = (float(w @ mus[urth].values) - DEFAULT_RISK_FREE_RATE) / np.sqrt(w @ S.values @ w)
    assert a["sharpe_capm"] == pytest.approx(expected)
    assert a["sharpe_capm"] != pytest.approx(b["sharpe_capm"], abs=0.01) and seen == [urth, spx]
    # realized numbers don't depend on the benchmark
    assert a["sharpe_historical"] == pytest.approx(b["sharpe_historical"]) and a["vol"] == pytest.approx(b["vol"])
    assert a["sortino"] is not None


def test_risk_metrics_empty_holdings_and_missing_history(monkeypatch):
    assert fw._risk_metrics({}, {}, "URTH") == {"sharpe_capm": None, "sharpe_historical": None, "sortino": None, "vol": None}
    monkeypatch.setattr(fw, "portfolio_returns", lambda h: pd.Series(dtype="float64"))
    monkeypatch.setattr(fw, "mu_cov", lambda t, b=None, *a, **k: (pd.Series(dtype="float64"), pd.DataFrame()))
    assert fw._risk_metrics({"A": 1.0}, {"A": 1.0}, "URTH")["sharpe_capm"] is None


# --- endpoint ---------------------------------------------------------------------------------------------

@pytest.fixture
def client(world):
    app = FastAPI()
    app.include_router(fw_api.router, prefix="/api/finance")
    return TestClient(app)


def test_forward_whatif_endpoint(client):
    body = client.post("/api/finance/scenarios/forward-whatif",
                       json={"ticker": "NEWCO", "action": "buy", "eur_amount": 1000, "benchmark": "SPY"}).json()

    assert body["benchmark"] == "SPY" and body["bucket"]["bucket"] == "single_stocks"
    assert len(body["bucket_table"]) == 4 and set(body["metrics"]) == {"sharpe_capm", "sharpe_historical", "sortino", "vol"}


def test_forward_whatif_endpoint_errors_are_422_with_a_message(client):
    r = client.post("/api/finance/scenarios/forward-whatif", json={"ticker": "NEWCO", "action": "sell", "eur_amount": 500})
    assert r.status_code == 422 and "don't hold NEWCO" in r.json()["detail"]
    assert client.post("/api/finance/scenarios/forward-whatif", json={"ticker": "ADBE", "action": "buy"}).status_code == 422  # missing amount
