"""Tests for Chunk 9's Anlage KAP summary: Zeile aggregation, the Sparerpauschbetrag
cap, and the dividend / foreign-income sub-components it feeds from. Monkeypatched;
no ledger/disk/network I/O.
"""
from __future__ import annotations

from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import tax as tax_api
from modules.finance import kap_form
from modules.finance import verlustverrechnung as vv
from modules.finance import vorabpauschale as vp


class _Txn:
    def __init__(self, ticker, action, quantity, price, year, month=6, day=1):
        self.ticker, self.action, self.quantity, self.price = ticker, action, quantity, price
        self.date = date(year, month, day)


class _Pos:
    def __init__(self, type_="equity", currency="USD"):
        self.type, self.currency = type_, currency


def _pot(gains=0.0, losses=0.0, prior=0.0):
    net = round(gains - losses - prior, 2)
    return {"label": "x", "this_year_gains": gains, "this_year_losses": losses,
            "prior_carryforward": prior, "net_balance": net, "new_carryforward": round(max(0.0, -net), 2)}


def _pots(aktien=None, sonstige=None, spek=None, tax_free_excl=0.0):
    return {
        "tax_year": 2026,
        "pots": {"aktien": _pot(**(aktien or {})), "sonstige": _pot(**(sonstige or {})), "spekulation_23": _pot(**(spek or {}))},
        "tax_free_crypto_excluded_eur": tax_free_excl,
        "note": "the spekulation_23 pot is not an Anlage-KAP line",
    }


EMPTY_VORAB = {"tax_year": 2026, "basiszins": None, "rows": [], "total_taxable_eur": 0.0}


# --- _dividend_income ----------------------------------------------------------------------

def test_dividend_income_is_manual_needed_with_no_dividend_transactions(monkeypatch):
    monkeypatch.setattr(kap_form, "list_transactions", lambda: [])
    out = kap_form._dividend_income(2026)
    assert out["confidence"] == "manual_needed" and out["net_of_teilfreistellung"] == 0.0


def test_dividend_income_applies_teilfreistellung_only_to_fund_payouts(monkeypatch):
    txns = [_Txn("AAPL", "dividend", 1, 50.0, 2026), _Txn("VWCE.DE", "dividend", 1, 100.0, 2026)]
    monkeypatch.setattr(kap_form, "list_transactions", lambda: txns)
    monkeypatch.setattr(kap_form, "get_position", lambda t: {"AAPL": _Pos("equity"), "VWCE.DE": _Pos("etf")}[t])
    monkeypatch.setattr(kap_form, "resolve_bucket", lambda t: {"AAPL": "single_stocks", "VWCE.DE": "etf_foundation"}[t])
    monkeypatch.setattr(vp, "etf_metadata", lambda t: {"teilfreistellung": 0.30})

    out = kap_form._dividend_income(2026)

    assert out["gross"] == 150.0
    assert out["net_of_teilfreistellung"] == 50.0 + 100.0 * 0.70  # AAPL in full, VWCE.DE at 70%
    assert out["confidence"] == "confirmed"


def test_dividend_income_ignores_other_years(monkeypatch):
    monkeypatch.setattr(kap_form, "list_transactions", lambda: [_Txn("AAPL", "dividend", 1, 50.0, 2025)])
    assert kap_form._dividend_income(2026)["confidence"] == "manual_needed"


# --- _foreign_capital_income -----------------------------------------------------------------

def test_foreign_income_excludes_eur_and_crypto(monkeypatch):
    rows = [
        {"ticker": "AAPL", "date_sold": "2026-04-01", "realized_gain_eur": "-100.0"},   # USD, Aktien -> counted
        {"ticker": "VWCE.DE", "date_sold": "2026-03-01", "realized_gain_eur": "50.0"},  # EUR -> excluded
        {"ticker": "BTC-USD", "date_sold": "2026-06-01", "realized_gain_eur": "900.0"},  # crypto -> excluded
    ]
    monkeypatch.setattr(kap_form, "read_rows", lambda path: rows)
    monkeypatch.setattr(vv, "classify_pot", lambda t: {"AAPL": "aktien", "VWCE.DE": "sonstige", "BTC-USD": "spekulation_23"}[t])
    monkeypatch.setattr(kap_form, "_ticker_currency", lambda t: {"AAPL": "USD", "VWCE.DE": "EUR", "BTC-USD": "USD"}[t])
    monkeypatch.setattr(kap_form, "list_transactions", lambda: [])

    out = kap_form._foreign_capital_income(2026)

    assert out["amount_eur"] == -100.0


# --- kap_summary: Zeile aggregation + Sparerpauschbetrag cap -----------------------------------

def _patch_common(monkeypatch, pots, vorab=EMPTY_VORAB, dividends=None, foreign=None):
    monkeypatch.setattr(vv, "current_pots", lambda tax_year, prior=None: pots)
    monkeypatch.setattr(vp, "compute_for_year", lambda tax_year=None: vorab)
    monkeypatch.setattr(kap_form, "_dividend_income", lambda y: dividends or {
        "gross": 0.0, "net_of_teilfreistellung": 0.0, "confidence": "manual_needed", "note": "no dividends",
    })
    monkeypatch.setattr(kap_form, "_foreign_capital_income", lambda y: foreign or {
        "amount_eur": 0.0, "confidence": "confirmed", "note": "none",
    })


def _line(result, zeile):
    return next(l for l in result["lines"] if l["zeile_number"] == zeile)


def test_zeile_8_9_is_the_sonstige_pots_net_gain(monkeypatch):
    pots = _pots(sonstige={"gains": 500.0, "losses": 100.0})
    _patch_common(monkeypatch, pots)
    out = kap_form.kap_summary(2026, prior_carryforwards={})
    assert _line(out, "8-9")["amount_eur"] == 400.0


def test_zeile_20_sums_aktien_and_sonstige_losses_only(monkeypatch):
    pots = _pots(aktien={"losses": 150.0}, sonstige={"losses": 30.0}, spek={"losses": 999.0})
    _patch_common(monkeypatch, pots)
    out = kap_form.kap_summary(2026, prior_carryforwards={})
    assert _line(out, "20")["amount_eur"] == 180.0  # the spekulation_23 loss is NOT Anlage KAP


def test_zeile_48_49_report_the_new_carryforward(monkeypatch):
    pots = _pots(aktien={"losses": 300.0, "prior": 50.0}, sonstige={"gains": 400.0})
    _patch_common(monkeypatch, pots)
    out = kap_form.kap_summary(2026, prior_carryforwards={})
    assert _line(out, "48")["amount_eur"] == 350.0  # 300 loss + 50 prior carryforward, no gain to absorb it
    assert _line(out, "49")["amount_eur"] == 0.0     # a net gain: nothing carries forward


def test_sparerpauschbetrag_is_capped_at_the_default_1000(monkeypatch):
    pots = _pots(sonstige={"gains": 5000.0})  # far more than the allowance
    _patch_common(monkeypatch, pots)
    out = kap_form.kap_summary(2026, prior_carryforwards={})
    assert out["sparerpauschbetrag"] == 1000
    assert _line(out, "16")["amount_eur"] == 1000.0  # capped, not the full 5000


def test_sparerpauschbetrag_cap_respects_an_override_below_the_default(monkeypatch):
    pots = _pots(sonstige={"gains": 5000.0})
    _patch_common(monkeypatch, pots)
    out = kap_form.kap_summary(2026, prior_carryforwards={}, sparerpauschbetrag=200)
    assert out["sparerpauschbetrag"] == 200
    assert _line(out, "16")["amount_eur"] == 200.0


def test_sparerpauschbetrag_below_taxable_income_uses_the_smaller_actual_income(monkeypatch):
    pots = _pots(sonstige={"gains": 300.0})  # less than the 1000 allowance
    _patch_common(monkeypatch, pots)
    out = kap_form.kap_summary(2026, prior_carryforwards={})
    assert _line(out, "16")["amount_eur"] == 300.0  # min(1000, 300)


def test_losses_do_not_consume_the_sparerpauschbetrag(monkeypatch):
    """A net loss contributes 0 (not a negative number) to the taxable base — only
    the sonstige pot's gain counts, so the allowance used is just that gain."""
    pots = _pots(aktien={"losses": 400.0}, sonstige={"gains": 100.0})
    _patch_common(monkeypatch, pots)
    out = kap_form.kap_summary(2026, prior_carryforwards={})
    assert _line(out, "16")["amount_eur"] == 100.0


def test_non_kap_note_reports_spekulation_23_separately(monkeypatch):
    pots = _pots(spek={"gains": 4000.0}, tax_free_excl=3000.0)
    _patch_common(monkeypatch, pots)
    out = kap_form.kap_summary(2026, prior_carryforwards={})
    assert out["non_kap_note"]["amount_eur"] == 4000.0
    assert "Anlage SO" in out["non_kap_note"]["computation_note"]
    assert "8-9" not in [l["zeile_number"] for l in out["lines"] if "spekulation" in l["label"].lower()]


def test_vorabpauschale_line_reflects_manual_needed_rows(monkeypatch):
    pots = _pots()
    vorab = {"tax_year": 2026, "basiszins": None, "rows": [
        {"ticker": "VWCE.DE", "confidence": "manual_needed", "note": "x"},
    ], "total_taxable_eur": 0.0}
    _patch_common(monkeypatch, pots, vorab=vorab)
    out = kap_form.kap_summary(2026, prior_carryforwards={})
    assert _line(out, "41-45")["confidence"] == "manual_needed"


def test_default_tax_year_is_the_current_year(monkeypatch):
    pots = _pots()
    _patch_common(monkeypatch, pots)
    out = kap_form.kap_summary(prior_carryforwards={})
    assert out["tax_year"] == date.today().year


# --- API -----------------------------------------------------------------------------------

def test_kap_summary_endpoint(monkeypatch):
    pots = _pots(sonstige={"gains": 200.0})
    _patch_common(monkeypatch, pots)
    app = FastAPI()
    app.include_router(tax_api.router, prefix="/api/finance")
    client = TestClient(app)

    body = client.get("/api/finance/tax/kap-summary?year=2026").json()
    assert body["tax_year"] == 2026
    assert len(body["lines"]) == 8
    assert body["disclaimer"]

    overridden = client.get("/api/finance/tax/kap-summary?year=2026&sparerpauschbetrag=50").json()
    assert overridden["sparerpauschbetrag"] == 50
