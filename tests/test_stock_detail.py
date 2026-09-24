"""Tests for modules/finance/stock_detail.py and its endpoints (Chunk 4).

yfinance and the price cache are monkeypatched — deterministic and network-free.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import stock_detail as sd_api
from modules.finance import stock_detail as sd


def _closes(n=400, start=100.0, step=0.5) -> pd.Series:
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    return pd.Series(start + np.arange(n) * step, index=idx)


FULL_INFO = {
    "longName": "Adobe Inc.", "sector": "Technology", "industry": "Software", "exchange": "NMS",
    "currency": "USD", "quoteType": "EQUITY", "marketCap": 150e9, "forwardPE": 21.5,
    "revenueGrowth": 0.11, "operatingMargins": 0.36, "dividendRate": 2.0,
    "fiftyTwoWeekLow": 100.0, "fiftyTwoWeekHigh": 400.0, "freeCashflow": 6e9,
}


@pytest.fixture
def prices(monkeypatch):
    closes = _closes()
    monkeypatch.setattr(sd, "get_closes", lambda t: closes)
    monkeypatch.setattr(sd, "get_returns", lambda t: closes.pct_change().dropna())
    monkeypatch.setattr("modules.finance.risk.beta_vs", lambda rets, bench: 1.25)
    return closes


def test_fundamentals_full(monkeypatch, prices):
    monkeypatch.setattr(sd, "get_info", lambda t: FULL_INFO)
    f = sd.fundamentals("ADBE", benchmark="SPY")

    assert f["name"] == "Adobe Inc." and f["sector"] == "Technology"
    assert f["market_cap"] == 150e9 and f["pe_forward"] == 21.5
    assert f["revenue_growth"] == 0.11 and f["ebit_margin"] == 0.36
    assert f["fcf_yield"] == pytest.approx(6e9 / 150e9)
    assert f["dividend_yield"] == pytest.approx(2.0 / f["price"])
    assert f["week52_position"] == pytest.approx((f["price"] - 100.0) / 300.0)
    assert f["beta"] == 1.25 and f["beta_benchmark"] == "SPY"
    assert f["day_change_pct"] == pytest.approx(0.5 / (prices.iloc[-2]))


def test_fundamentals_missing_fields_graceful(monkeypatch):
    """yfinance returns partial data, junk values, or nothing — never a crash."""
    monkeypatch.setattr(sd, "get_closes", lambda t: pd.Series(dtype="float64"))
    monkeypatch.setattr(sd, "get_returns", lambda t: pd.Series(dtype="float64"))

    # Partial: only a name. Junk: strings / infinities where numbers belong.
    monkeypatch.setattr(sd, "get_info", lambda t: {"longName": "Thin Co", "marketCap": "Infinity", "forwardPE": "n/a"})
    f = sd.fundamentals("THIN")
    assert f["name"] == "Thin Co"
    for key in ("market_cap", "pe_forward", "revenue_growth", "ebit_margin", "dividend_yield",
                "week52_position", "beta", "fcf_yield", "price", "day_change_pct", "sector", "as_of"):
        assert f[key] is None, key

    # Nothing at all.
    monkeypatch.setattr(sd, "get_info", lambda t: {})
    empty = sd.fundamentals("NOPE")
    assert empty["ticker"] == "NOPE" and empty["name"] is None and empty["market_cap"] is None


def test_position_summary_not_held(monkeypatch):
    monkeypatch.setattr(sd, "current_holdings", lambda: {"MSFT": 3.0})
    assert sd.position_summary("ADBE") is None


def test_position_summary_held(monkeypatch):
    from datetime import date, timedelta
    from types import SimpleNamespace

    monkeypatch.setattr(sd, "current_holdings", lambda: {"ADBE": 10.0})
    monkeypatch.setattr(sd, "cost_basis", lambda t: (300.0, 3000.0))
    monkeypatch.setattr(sd, "latest_price_eur", lambda t: SimpleNamespace(eur_price=400.0, fx_stale=False))
    monkeypatch.setattr(sd, "first_transaction_date", lambda t: date.today() - timedelta(days=45))
    monkeypatch.setattr(sd, "get_position", lambda t: SimpleNamespace(name="Adobe Inc."))
    monkeypatch.setattr(
        "modules.finance.dashboard.holdings_with_day_change",
        lambda: [{"ticker": "ADBE", "weight": 0.25}, {"ticker": "MSFT", "weight": 0.75}],
    )

    p = sd.position_summary("adbe")  # lookup is case-insensitive

    assert p["cost_basis"] == 3000.0 and p["current_value"] == 4000.0
    assert p["pnl"] == 1000.0 and p["pnl_pct"] == pytest.approx(1 / 3)
    assert p["weight"] == 0.25 and p["days_held"] == 45


def test_price_series_periods(monkeypatch, prices):
    week = sd.price_series("X", "1w")
    assert 4 <= len(week["points"]) <= 6
    year = sd.price_series("X", "1y")
    assert len(year["points"]) > len(week["points"])
    assert year["change_pct"] > 0
    ytd = sd.price_series("X", "ytd")
    assert ytd["points"][0]["date"] >= f"{pd.Timestamp.today().year}-01-01"
    assert len(sd.price_series("X", "all")["points"]) == len(prices)
    # Unknown period falls back to 1y instead of raising.
    assert sd.price_series("X", "bogus")["period"] == "1y"


def test_price_series_downsamples_long_history(monkeypatch):
    long = _closes(n=3000)
    monkeypatch.setattr(sd, "get_closes", lambda t: long)
    pts = sd.price_series("X", "all")["points"]
    assert len(pts) <= sd._MAX_POINTS + 1
    assert pts[-1]["close"] == round(float(long.iloc[-1]), 4)  # latest point always kept


def test_price_series_no_data(monkeypatch):
    monkeypatch.setattr(sd, "get_closes", lambda t: pd.Series(dtype="float64"))
    assert sd.price_series("X") == {"period": "1y", "points": [], "change_pct": None}


# --- 24h parquet cache ----------------------------------------------------------

@pytest.fixture
def cache_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(sd, "FUNDAMENTALS_CACHE_DIR", tmp_path / "fundamentals_cache")
    return tmp_path / "fundamentals_cache"


def test_info_cached_for_24h(monkeypatch, cache_dir):
    calls = []
    monkeypatch.setattr(sd, "_fetch_info", lambda t: calls.append(t) or {"longName": "Adobe", "marketCap": 1.0})

    assert sd.get_info("ADBE")["longName"] == "Adobe"
    assert sd.get_info("ADBE")["longName"] == "Adobe"
    assert calls == ["ADBE"]  # second call served from data/fundamentals_cache/ADBE.parquet
    assert (cache_dir / "ADBE.parquet").exists()

    # Expire it: a fresh fetch happens.
    monkeypatch.setattr(sd, "FUNDAMENTALS_TTL_SECONDS", -1)
    sd.get_info("ADBE")
    assert calls == ["ADBE", "ADBE"]


def test_failed_lookup_not_cached_and_stale_served(monkeypatch, cache_dir):
    monkeypatch.setattr(sd, "_fetch_info", lambda t: {})
    assert sd.get_info("NOPE") == {}
    assert not (cache_dir / "NOPE.parquet").exists()  # an empty result would pin "—" for a day

    # A stale snapshot beats nothing when yfinance is down.
    sd._write_cache("ADBE", {"longName": "Adobe", "marketCap": 1.0})
    monkeypatch.setattr(sd, "FUNDAMENTALS_TTL_SECONDS", -1)
    assert sd.get_info("ADBE")["longName"] == "Adobe"


# --- endpoints ----------------------------------------------------------------

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(sd_api.router, prefix="/api/finance")
    return TestClient(app)


def test_stock_detail_endpoint(client, monkeypatch, prices):
    monkeypatch.setattr(sd, "get_info", lambda t: FULL_INFO)
    monkeypatch.setattr(sd, "current_holdings", lambda: {})

    body = client.get("/api/finance/stock-detail/ADBE?period=3m&benchmark=SPY").json()

    assert body["ticker"] == "ADBE"
    assert body["fundamentals"]["name"] == "Adobe Inc."
    assert body["position"] is None            # not held -> the card is hidden
    assert body["series"]["period"] == "3m" and body["series"]["points"]
    assert client.get("/api/finance/stock-detail/ADBE?period=nope").status_code == 422


def test_stock_universe_endpoint_orders_held_then_watchlist(client, monkeypatch):
    from types import SimpleNamespace

    from modules.finance import positions, watchlist

    monkeypatch.setattr(positions, "current_holdings", lambda: {"NVDA": 1.0, "AAPL": 2.0})
    monkeypatch.setattr(positions, "get_position", lambda t: SimpleNamespace(name=f"{t} Inc"))
    monkeypatch.setattr(watchlist, "flat_entries", lambda: [
        {"ticker": "ADBE", "name": "Adobe"}, {"ticker": "AAPL", "name": "Apple"},
        {"ticker": "^GSPC", "name": "S&P 500"}, {"ticker": "EURUSD=X", "name": "EURUSD"},
        {"ticker": "NKE", "name": ""},
    ])

    body = client.get("/api/finance/stock-universe").json()

    assert [h["ticker"] for h in body["held"]] == ["AAPL", "NVDA"]
    # Held names are not repeated in the watchlist group; indices / FX are dropped.
    assert body["watchlist"] == [{"ticker": "ADBE", "name": "Adobe"}, {"ticker": "NKE", "name": "NKE"}]


def test_stock_universe_empty(client, monkeypatch):
    from modules.finance import positions, watchlist

    monkeypatch.setattr(positions, "current_holdings", lambda: {})
    monkeypatch.setattr(watchlist, "flat_entries", lambda: [])
    assert client.get("/api/finance/stock-universe").json() == {"held": [], "watchlist": []}
