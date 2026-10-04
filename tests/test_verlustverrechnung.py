"""Tests for Chunk 9's Verlustverrechnungstopf: bucket-based pot classification,
this-year netting against a prior carryforward, the tax-free-crypto exclusion,
and the manual carryforward store. Monkeypatched; no ledger/disk/network I/O.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import tax as tax_api
from modules.finance import verlustverrechnung as vv


def _row(ticker: str, gain: float, holding_days: int, sold: str = "2026-06-01") -> dict:
    return {"ticker": ticker, "date_sold": sold, "realized_gain_eur": str(gain), "holding_days": str(holding_days)}


class _Pos:
    def __init__(self, type_: str):
        self.type = type_


# --- classify_pot ----------------------------------------------------------------------------

def test_classify_pot_follows_the_bucket_first(monkeypatch):
    buckets = {"AAPL": "single_stocks", "VWCE.DE": "etf_foundation", "BTC-USD": "crypto"}
    monkeypatch.setattr(vv, "resolve_bucket", lambda t: buckets[t])
    assert vv.classify_pot("AAPL") == "aktien"
    assert vv.classify_pot("VWCE.DE") == "sonstige"
    assert vv.classify_pot("BTC-USD") == "spekulation_23"


def test_classify_pot_wild_card_falls_back_to_instrument_type(monkeypatch):
    monkeypatch.setattr(vv, "resolve_bucket", lambda t: "wild_cards")
    positions = {"OKLO": _Pos("equity"), "SOME-ETF": _Pos("etf"), "DOGE-USD": _Pos("crypto")}
    monkeypatch.setattr(vv, "get_position", lambda t: positions.get(t))
    assert vv.classify_pot("OKLO") == "aktien"
    assert vv.classify_pot("SOME-ETF") == "sonstige"
    assert vv.classify_pot("DOGE-USD") == "spekulation_23"


def test_classify_pot_unassigned_no_position_guesses_crypto_by_suffix(monkeypatch):
    monkeypatch.setattr(vv, "resolve_bucket", lambda t: "unassigned")
    monkeypatch.setattr(vv, "get_position", lambda t: None)
    assert vv.classify_pot("SOL-EUR") == "spekulation_23"
    assert vv.classify_pot("RANDOM") == "aktien"  # uncertain calls default to the equity case


# --- current_pots ------------------------------------------------------------------------------

def test_current_pots_nets_per_pot_and_excludes_tax_free_crypto(monkeypatch):
    rows = [
        _row("AAPL", -150.0, 790),                  # aktien: a loss
        _row("VWCE.DE", 400.0, 776),                 # sonstige: a gain
        _row("BTC-USD", 4000.0, 147),                 # spekulation_23: taxable (< 365d)
        _row("BTC-USD", 3000.0, 762),                 # spekulation_23: tax-free (>= 365d) -> excluded
        _row("MSFT", 999.0, 10, sold="2025-12-31"),   # wrong tax year -> ignored
    ]
    monkeypatch.setattr(vv, "read_rows", lambda path: rows)
    monkeypatch.setattr(vv, "resolve_bucket", lambda t: {
        "AAPL": "single_stocks", "VWCE.DE": "etf_foundation", "BTC-USD": "crypto",
    }[t])

    out = vv.current_pots(2026, prior_carryforwards={})

    assert out["pots"]["aktien"] == {
        "label": "Aktien", "this_year_gains": 0.0, "this_year_losses": 150.0,
        "prior_carryforward": 0.0, "net_balance": -150.0, "new_carryforward": 150.0,
    }
    assert out["pots"]["sonstige"]["net_balance"] == 400.0 and out["pots"]["sonstige"]["new_carryforward"] == 0.0
    assert out["pots"]["spekulation_23"]["this_year_gains"] == 4000.0
    assert out["tax_free_crypto_excluded_eur"] == 3000.0


def test_current_pots_applies_an_explicit_prior_carryforward(monkeypatch):
    monkeypatch.setattr(vv, "read_rows", lambda path: [_row("AAPL", 100.0, 10)])
    monkeypatch.setattr(vv, "resolve_bucket", lambda t: "single_stocks")

    out = vv.current_pots(2026, prior_carryforwards={"aktien": 80.0})

    assert out["pots"]["aktien"]["net_balance"] == 20.0
    assert out["pots"]["aktien"]["new_carryforward"] == 0.0


def test_current_pots_a_loss_still_carries_forward_past_this_years_gain(monkeypatch):
    monkeypatch.setattr(vv, "read_rows", lambda path: [_row("AAPL", 50.0, 10)])
    monkeypatch.setattr(vv, "resolve_bucket", lambda t: "single_stocks")

    out = vv.current_pots(2026, prior_carryforwards={"aktien": 200.0})

    assert out["pots"]["aktien"]["net_balance"] == -150.0
    assert out["pots"]["aktien"]["new_carryforward"] == 150.0


def test_current_pots_reads_the_persisted_store_when_no_override_given(monkeypatch):
    monkeypatch.setattr(vv, "read_rows", lambda path: [])
    monkeypatch.setattr(vv, "get_carryforwards", lambda: {"aktien": 10.0, "sonstige": 0.0, "spekulation_23": 0.0})

    out = vv.current_pots(2026)

    assert out["pots"]["aktien"]["prior_carryforward"] == 10.0


# --- carryforward store --------------------------------------------------------------------

def test_carryforward_store_roundtrips_and_merges(tmp_path, monkeypatch):
    monkeypatch.setattr(vv, "TAX_CARRYFORWARDS_FILE", tmp_path / "tax_carryforwards.json")

    assert vv.get_carryforwards() == {"aktien": 0.0, "sonstige": 0.0, "spekulation_23": 0.0}

    merged = vv.set_carryforwards({"aktien": 250.0, "unknown_key": 999})
    assert merged["aktien"] == 250.0 and "unknown_key" not in merged
    assert vv.get_carryforwards()["aktien"] == 250.0

    # a second, partial update merges rather than resetting the untouched pots
    vv.set_carryforwards({"sonstige": 5.0})
    assert vv.get_carryforwards() == {"aktien": 250.0, "sonstige": 5.0, "spekulation_23": 0.0}


# --- API ---------------------------------------------------------------------------------------

def test_loss_pots_and_carryforward_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(vv, "TAX_CARRYFORWARDS_FILE", tmp_path / "tax_carryforwards.json")
    monkeypatch.setattr(vv, "read_rows", lambda path: [_row("AAPL", -50.0, 10)])
    monkeypatch.setattr(vv, "resolve_bucket", lambda t: "single_stocks")
    app = FastAPI()
    app.include_router(tax_api.router, prefix="/api/finance")
    client = TestClient(app)

    body = client.get("/api/finance/tax/loss-pots?year=2026").json()
    assert body["pots"]["aktien"]["this_year_losses"] == 50.0

    client.put("/api/finance/tax/loss-pots/carryforward", json={"aktien": 123.0})
    body2 = client.get("/api/finance/tax/loss-pots?year=2026").json()
    assert body2["pots"]["aktien"]["prior_carryforward"] == 123.0
    assert client.get("/api/finance/tax/loss-pots/carryforward").json()["aktien"] == 123.0
