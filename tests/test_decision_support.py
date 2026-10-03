"""Tests for the Chunk 7 additions to modules/finance/decision_support.py:
quarterly cadence alert, sale tax notes, and the security-level rebalance.

Pure-function inputs (positions / prices / lots) — no network, no ledger, no price cache.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import decisions as decisions_api
from modules.finance import decision_support as ds

TODAY = date(2026, 9, 26)


# --- quarterly cadence ------------------------------------------------------------------

@pytest.mark.parametrize("d, quarter", [
    (date(2026, 1, 1), "Q1 2026"),
    (date(2026, 1, 7), "Q1 2026"),   # last day of the 7-day window
    (date(2026, 4, 1), "Q2 2026"),
    (date(2026, 7, 3), "Q3 2026"),
    (date(2026, 10, 7), "Q4 2026"),
    (date(2027, 1, 1), "Q1 2027"),
])
def test_quarterly_cadence_fires_in_first_seven_days(d, quarter):
    alert = ds.quarterly_cadence_alert(d)

    assert alert["type"] == "quarterly_review" and alert["quarter"] == quarter
    assert alert["rationale"] == f"{quarter} rebalance review due — even without drift, review positions per your quarterly cadence"
    assert alert["due_date"] == d.replace(day=1).isoformat()


@pytest.mark.parametrize("d", [
    date(2026, 1, 8),    # first day past the window
    date(2026, 1, 15),   # mid-January
    date(2026, 1, 28),   # late January
    date(2026, 2, 1), date(2026, 3, 1), date(2026, 5, 3), date(2026, 8, 2),   # not a quarter-start month
    date(2026, 12, 31), date(2026, 9, 26),
])
def test_quarterly_cadence_silent_outside_window(d):
    assert ds.quarterly_cadence_alert(d) is None


def test_quarterly_alert_fires_regardless_of_drift_and_merges_into_alerts():
    positions = [{"ticker": "VWCE.DE", "quantity": 10, "bucket": "etf_foundation", "type": "etf"}]
    prices = {"VWCE.DE": 100.0}

    in_window = ds.decision_alerts(positions, prices, as_of=date(2026, 4, 2))
    out_of_window = ds.decision_alerts(positions, prices, as_of=date(2026, 4, 20))

    assert [a["type"] for a in in_window][0] == "quarterly_review"  # first in the list
    assert all(a["type"] != "quarterly_review" for a in out_of_window)
    # the drift/concentration alerts are still there alongside it
    assert [a for a in in_window if a["type"] != "quarterly_review"] == out_of_window


def test_decision_summary_counts_a_due_quarterly_review(monkeypatch):
    monkeypatch.setattr(ds, "current_positions_and_prices", lambda: ([], {}))
    monkeypatch.setattr(ds, "harvest_candidates", lambda p, pr: [])

    quiet = ds.decision_summary(as_of=date(2026, 5, 10))
    due = ds.decision_summary(as_of=date(2026, 7, 2))

    assert quiet["quarterly_review"] is None and due["quarterly_review"]["quarter"] == "Q3 2026"
    assert due["rebalance_count"] == quiet["rebalance_count"] + 1


# --- sale tax notes ---------------------------------------------------------------------------

def _lot(days_ago, qty):
    return {"date": TODAY - timedelta(days=days_ago), "quantity": qty, "unit_cost": 100.0}


def test_stock_note_is_abgeltungsteuer_whatever_the_holding_period():
    note = ds.sale_tax_note("NVDA", "equity", 3.2, TODAY, [_lot(120, 10)])
    assert note == "Held 120 days — Abgeltungsteuer applies"
    # a 400-day-old stock lot gets the same treatment (no Spekulationsfrist for stocks)
    assert "Abgeltungsteuer applies" in ds.sale_tax_note("NVDA", "equity", 1, TODAY, [_lot(400, 10)])
    assert "Spekulationsfrist" not in ds.sale_tax_note("VWCE.DE", "etf", 1, TODAY, [_lot(900, 10)])


def test_crypto_note_inside_and_past_the_spekulationsfrist():
    young = ds.sale_tax_note("ETH-USD", "crypto", 1.0, TODAY, [_lot(120, 5)])
    assert young.startswith("Held 120 days — inside the Spekulationsfrist") and "tax-free in 245 days" in young

    old = ds.sale_tax_note("BTC-USD", "crypto", 1.0, TODAY, [_lot(400, 5)])
    assert old == "Held 400 days — Spekulationsfrist met (crypto only), gains tax-free"


def test_crypto_note_follows_fifo_across_lots():
    lots = [_lot(500, 2.0), _lot(60, 3.0)]  # oldest first

    only_old = ds.sale_tax_note("BTC-USD", "crypto", 1.5, TODAY, lots)   # fully inside the old lot
    mixed = ds.sale_tax_note("BTC-USD", "crypto", 3.0, TODAY, lots)      # 2.0 old + 1.0 young
    assert "Spekulationsfrist met" in only_old
    assert "2 units held 365+ days (tax-free)" in mixed and "1 units inside the Spekulationsfrist" in mixed
    assert "youngest 60 days" in mixed


def test_tax_note_without_history():
    assert ds.sale_tax_note("X", "equity", 1, TODAY, []) == "Abgeltungsteuer applies"
    assert "unknown" in ds.sale_tax_note("BTC-USD", "crypto", 1, TODAY, [])


# --- security-level rebalance ---------------------------------------------------------------------

def _pos(t, q, bucket, typ="equity"):
    return {"ticker": t, "quantity": q, "bucket": bucket, "type": typ}


@pytest.fixture
def crypto_heavy(monkeypatch):
    """Portfolio 10,000: ETF 40% (vs 49), stocks 20%, crypto 34% (vs 24, >30% trigger), wild 6%.
    BTC is an old (400d) crypto lot, ETH a young (100d) one."""
    positions = [
        _pos("VWCE.DE", 40, "etf_foundation", "etf"),
        _pos("ADBE", 20, "single_stocks"),
        _pos("BTC-USD", 14, "crypto", "crypto"),
        _pos("ETH-USD", 20, "crypto", "crypto"),
        _pos("TSLA", 6, "wild_cards"),
    ]
    prices = {"VWCE.DE": 100.0, "ADBE": 100.0, "BTC-USD": 100.0, "ETH-USD": 100.0, "TSLA": 100.0}
    lots = {"BTC-USD": [_lot(400, 14)], "ETH-USD": [_lot(100, 20)], "VWCE.DE": [_lot(50, 40)],
            "ADBE": [_lot(200, 20)], "TSLA": [_lot(30, 6)]}
    monkeypatch.setattr(ds, "cost_basis", lambda t: (90.0, 90.0 * 100))
    pv = ds.portfolio_value(positions, prices)
    recs = ds.rebalance_recommendations(ds.bucket_allocations(positions, prices), pv)
    return positions, prices, recs, pv, (lambda t: lots.get(t, []))


def test_recs_fixture_is_the_scenario_we_think_it_is(crypto_heavy):
    _, _, recs, pv, _ = crypto_heavy
    assert pv == 10000
    assert {(r["bucket"], r["action"]) for r in recs} == {("etf_foundation", "buy"), ("crypto", "sell"), ("crypto", "trim_to_target")}


def test_default_crypto_rule_is_tax_free_first():
    assert ds.CRYPTO_SELL_ORDER == "tax_free_first"


def test_security_level_pairs_default_sells_tax_free_crypto_first(crypto_heavy):
    positions, prices, recs, pv, lots_fn = crypto_heavy

    trades = ds.security_level_rebalance(positions, prices, recs, pv, today=TODAY, lots_fn=lots_fn)
    sells = [t for t in trades if t["action"] == "sell"]
    buys = [t for t in trades if t["action"] == "buy"]

    assert [t["action"] for t in trades] == ["sell"] * len(sells) + ["buy"] * len(buys)  # sells first
    # crypto is over by 34% - 24% = €1,000; the 400-day BTC lot (past the Spekulationsfrist) goes first
    assert [(t["ticker"], t["units"], t["eur_amount"]) for t in sells] == [("BTC-USD", 10.0, 1000.0)]
    assert sells[0]["reason"] == "Crypto over by €1,000"
    assert sells[0]["tax_note"] == "Held 400 days — Spekulationsfrist met (crypto only), gains tax-free"
    assert sells[0]["text"] == "Sell 10 units BTC-USD (Crypto over by €1,000)"
    # proceeds go to the ETF Foundation (Section 0.3) — into the one ETF held
    assert [(t["ticker"], t["eur_amount"], t["units"]) for t in buys] == [("VWCE.DE", 1000.0, 10.0)]
    assert "Section 0.3" in buys[0]["reason"]
    assert sum(t["eur_amount"] for t in sells) == pytest.approx(sum(t["eur_amount"] for t in buys))


def test_crypto_sell_order_switch_can_still_prefer_the_youngest(crypto_heavy, monkeypatch):
    positions, prices, recs, pv, lots_fn = crypto_heavy
    monkeypatch.setattr(ds, "CRYPTO_SELL_ORDER", "youngest_first")

    sells = [t for t in ds.security_level_rebalance(positions, prices, recs, pv, today=TODAY, lots_fn=lots_fn) if t["action"] == "sell"]

    assert [t["ticker"] for t in sells] == ["ETH-USD"]
    assert "inside the Spekulationsfrist" in sells[0]["tax_note"] and "tax-free in 265 days" in sells[0]["tax_note"]


def test_sell_spans_securities_when_one_position_is_not_enough(crypto_heavy):
    positions, prices, _, pv, lots_fn = crypto_heavy
    big = [{"bucket": "crypto", "action": "sell", "delta_eur": -2500.0}]

    trades = ds.security_level_rebalance(positions, prices, big, pv, today=TODAY, lots_fn=lots_fn)
    sells = [t for t in trades if t["action"] == "sell"]

    assert [(t["ticker"], t["eur_amount"]) for t in sells] == [("BTC-USD", 1400.0), ("ETH-USD", 1100.0)]
    # the €2,500 of proceeds all go to the ETF Foundation, as one line per ticker
    assert [(t["ticker"], t["eur_amount"]) for t in trades if t["action"] == "buy"] == [("VWCE.DE", 2500.0)]


def test_stock_sells_prefer_the_smallest_unrealized_gain_and_note_abgeltungsteuer(monkeypatch):
    positions = [_pos("AAA", 30, "single_stocks"), _pos("BBB", 30, "single_stocks"), _pos("VWCE.DE", 40, "etf_foundation", "etf")]
    prices = {"AAA": 100.0, "BBB": 100.0, "VWCE.DE": 100.0}
    monkeypatch.setattr(ds, "cost_basis", lambda t: ({"AAA": 90.0, "BBB": 40.0}.get(t, 100.0), 0.0))  # AAA has the smaller gain
    recs = [{"bucket": "single_stocks", "action": "sell", "delta_eur": -1000.0}]

    trades = ds.security_level_rebalance(positions, prices, recs, 10000.0, today=TODAY, lots_fn=lambda t: [_lot(120, 30)])

    assert trades[0]["ticker"] == "AAA" and trades[0]["units"] == 10.0
    assert trades[0]["tax_note"] == "Held 120 days — Abgeltungsteuer applies"


def test_stock_sells_take_a_loser_before_any_gainer(monkeypatch):
    positions = [_pos("WIN", 30, "single_stocks"), _pos("LOSE", 30, "single_stocks")]
    prices = {"WIN": 100.0, "LOSE": 100.0}
    monkeypatch.setattr(ds, "cost_basis", lambda t: ({"WIN": 50.0, "LOSE": 130.0}[t], 0.0))
    recs = [{"bucket": "single_stocks", "action": "sell", "delta_eur": -3500.0}]

    sells = [t for t in ds.security_level_rebalance(positions, prices, recs, 6000.0, today=TODAY, lots_fn=lambda t: [_lot(30, 30)])
             if t["action"] == "sell"]

    assert [t["ticker"] for t in sells] == ["LOSE", "WIN"]  # the position at a loss goes first


def test_buys_top_up_the_holding_furthest_below_its_equal_weight_share(monkeypatch):
    monkeypatch.setattr(ds, "cost_basis", lambda t: (100.0, 0.0))
    positions = [_pos("VWCE.DE", 30, "etf_foundation", "etf"), _pos("CSPX.L", 10, "etf_foundation", "etf"),
                 _pos("ADBE", 60, "single_stocks")]
    prices = {"VWCE.DE": 100.0, "CSPX.L": 100.0, "ADBE": 100.0}
    # ETF bucket = 4000 of 10000; equal-weight target each = 0.49 * 10000 / 2 = 2450 -> CSPX is 2450-1000 short, VWCE 0
    recs = [{"bucket": "etf_foundation", "action": "buy", "delta_eur": 900.0}]

    buys = ds.security_level_rebalance(positions, prices, recs, 10000.0, today=TODAY, lots_fn=lambda t: [])

    assert [(t["ticker"], t["eur_amount"], t["units"]) for t in buys] == [("CSPX.L", 900.0, 9.0)]
    assert buys[0]["reason"] == "ETF Foundation under by €900" and buys[0]["tax_note"] == "no tax on a purchase"


def test_buy_into_an_empty_bucket_suggests_its_primary_ticker(monkeypatch):
    positions = [_pos("ADBE", 100, "single_stocks")]
    prices = {"ADBE": 100.0}
    monkeypatch.setattr(ds, "primary_ticker_for_bucket", lambda b: "VWCE.DE" if b == "etf_foundation" else None)
    monkeypatch.setattr(ds, "latest_price", lambda t: 80.0)  # VWCE isn't held -> priced fresh
    recs = [{"bucket": "etf_foundation", "action": "buy", "delta_eur": 4000.0}]

    buys = ds.security_level_rebalance(positions, prices, recs, 10000.0, today=TODAY, lots_fn=lambda t: [])

    assert [(t["ticker"], t["units"], t["eur_amount"]) for t in buys] == [("VWCE.DE", 50.0, 4000.0)]


def test_no_drift_means_no_trades():
    positions = [_pos("VWCE.DE", 10, "etf_foundation", "etf")]
    assert ds.security_level_rebalance(positions, {"VWCE.DE": 100.0}, [], 1000.0, today=TODAY) == []
    assert ds.security_level_rebalance([], {}, [{"bucket": "crypto", "action": "sell", "delta_eur": -5}], 0.0, today=TODAY) == []


def test_primary_ticker_is_the_first_listed_for_the_bucket(monkeypatch):
    from modules.finance import buckets

    monkeypatch.setattr(buckets, "_load_ticker_bucket_map", lambda *a, **k: {"VWCE.DE": "etf_foundation", "CSPX.L": "etf_foundation", "AAPL": "single_stocks"})
    assert ds.primary_ticker_for_bucket("etf_foundation") == "VWCE.DE"
    assert ds.primary_ticker_for_bucket("crypto") is None


# --- endpoints -----------------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch, crypto_heavy):
    positions, prices, _, _, lots_fn = crypto_heavy
    monkeypatch.setattr(ds, "current_positions_and_prices", lambda: (positions, prices))
    monkeypatch.setattr(ds, "open_lots", lots_fn)
    monkeypatch.setattr(ds, "harvest_candidates", lambda p, pr: [])
    app = FastAPI()
    app.include_router(decisions_api.router, prefix="/api/finance")
    return TestClient(app)


def test_rebalance_endpoint_includes_security_level_pairs_and_quarterly(client):
    body = client.get("/api/finance/decisions/rebalance?as_of=2026-01-03").json()

    assert {r["bucket"] for r in body["recommendations"]} >= {"crypto", "etf_foundation"}  # bucket-level output unchanged
    assert [p["action"] for p in body["security_level_pairs"]][0] == "sell"
    assert all({"action", "ticker", "units", "eur_amount", "reason", "tax_note"} <= set(p) for p in body["security_level_pairs"])
    assert body["security_level_note"] is None
    assert body["quarterly_review"]["quarter"] == "Q1 2026"
    assert client.get("/api/finance/decisions/rebalance?as_of=2026-01-20").json()["quarterly_review"] is None


def test_alerts_and_summary_endpoints_carry_the_quarterly_alert(client):
    alerts = client.get("/api/finance/decisions/alerts?as_of=2026-10-02").json()
    assert alerts["alerts"][0]["type"] == "quarterly_review" and alerts["count"] == len(alerts["alerts"])
    assert all(a["type"] != "quarterly_review" for a in client.get("/api/finance/decisions/alerts?as_of=2026-10-20").json()["alerts"])
    assert client.get("/api/finance/decisions/summary?as_of=2026-10-02").json()["quarterly_review"]["quarter"] == "Q4 2026"


def test_rebalance_endpoint_with_no_drift(monkeypatch):
    positions = [_pos("VWCE.DE", 49, "etf_foundation", "etf"), _pos("ADBE", 21, "single_stocks"),
                 _pos("BTC-USD", 24, "crypto", "crypto"), _pos("TSLA", 6, "wild_cards")]
    prices = {p["ticker"]: 100.0 for p in positions}
    monkeypatch.setattr(ds, "current_positions_and_prices", lambda: (positions, prices))
    app = FastAPI()
    app.include_router(decisions_api.router, prefix="/api/finance")

    body = TestClient(app).get("/api/finance/decisions/rebalance").json()

    assert body["security_level_pairs"] == [] and "no active drift" in body["security_level_note"]


def test_crypto_type_is_guessed_from_the_ticker_when_there_is_no_position_record(monkeypatch):
    monkeypatch.setattr(ds, "current_holdings", lambda: {"BTC-USD": 1.0, "AAPL": 2.0})
    monkeypatch.setattr(ds, "get_position", lambda t: None)   # ledger edited by hand: no Position rows
    monkeypatch.setattr(ds, "latest_price", lambda t: 100.0)
    from modules.finance import buckets
    monkeypatch.setattr(buckets, "resolve_bucket", lambda t: "crypto" if t == "BTC-USD" else "single_stocks")

    positions, _ = ds.current_positions_and_prices()

    assert {p["ticker"]: p["type"] for p in positions} == {"BTC-USD": "crypto", "AAPL": None}
