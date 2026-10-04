"""Tests for Chunk 9's Vorabpauschale: the InvStG §18 formula, its actual-gain
cap, Teilfreistellung, the thesaurierend-ETF filter, and the two config-yaml
readers. Monkeypatched; no network I/O (the two yaml-parsing tests touch a
tmp_path fixture file, nothing under data/ or config/).
"""
from __future__ import annotations

import pytest

from modules.finance import vorabpauschale as vp


# --- pure helpers --------------------------------------------------------------------------

def test_value_eur_on_or_after_picks_the_first_match_or_none():
    rows = [{"date": "2026-02-01", "value_eur": "100"}, {"date": "2026-03-01", "value_eur": "110"}]
    assert vp._value_eur_on_or_after(rows, "2026-01-01") == 100.0
    assert vp._value_eur_on_or_after(rows, "2026-02-15") == 110.0
    assert vp._value_eur_on_or_after(rows, "2026-04-01") is None


def test_value_eur_on_or_before_picks_the_last_match_or_none():
    rows = [{"date": "2026-02-01", "value_eur": "100"}, {"date": "2026-03-01", "value_eur": "110"}]
    assert vp._value_eur_on_or_before(rows, "2026-12-31") == 110.0
    assert vp._value_eur_on_or_before(rows, "2026-02-15") == 100.0
    assert vp._value_eur_on_or_before(rows, "2026-01-01") is None


# --- thesaurierend filter ------------------------------------------------------------------

def test_thesaurierend_filter_requires_etf_foundation_bucket_and_type(monkeypatch):
    monkeypatch.setattr("modules.finance.positions.current_holdings", lambda: {"VWCE.DE": 10, "AAPL": 5, "CSPX.L": 2})
    monkeypatch.setattr(vp, "resolve_bucket", lambda t: {"VWCE.DE": "etf_foundation", "AAPL": "single_stocks", "CSPX.L": "etf_foundation"}[t])
    monkeypatch.setattr(vp, "etf_metadata", lambda t: {"VWCE.DE": {"type": "thesaurierend", "teilfreistellung": 0.3},
                                                        "CSPX.L": {"type": "ausschüttend", "teilfreistellung": 0.3}}[t])
    assert vp._thesaurierend_etf_tickers() == ["VWCE.DE"]


# --- compute_for_year: formula, cap, Teilfreistellung -------------------------------------

@pytest.fixture
def one_etf(monkeypatch):
    monkeypatch.setattr(vp, "_thesaurierend_etf_tickers", lambda: ["VWCE.DE"])
    monkeypatch.setattr(vp, "etf_metadata", lambda t: {"type": "thesaurierend", "teilfreistellung": 0.3})
    monkeypatch.setattr(vp, "_distributions_eur", lambda t, y: 0.0)


def _rows(start, end):
    return {"VWCE.DE": [{"date": "2026-01-01", "value_eur": str(start)}, {"date": "2026-12-31", "value_eur": str(end)}]}


def test_formula_within_the_gain_cap(monkeypatch, one_etf):
    monkeypatch.setattr(vp, "basiszins_for_year", lambda y: 0.0229)
    monkeypatch.setattr(vp, "_daily_rows_by_ticker", lambda: _rows(10_000, 10_800))

    out = vp.compute_for_year(2026)
    row = out["rows"][0]

    base = 10_000 * 0.0229 * 0.7  # 160.30
    assert row["vorabpauschale"] == pytest.approx(round(base, 2))
    assert row["taxable_amount"] == pytest.approx(round(base * 0.7, 2))  # 30% Teilfreistellung
    assert row["confidence"] == "estimated"
    assert out["total_taxable_eur"] == row["taxable_amount"]


def test_formula_capped_at_the_actual_gain(monkeypatch, one_etf):
    monkeypatch.setattr(vp, "basiszins_for_year", lambda y: 0.0229)
    monkeypatch.setattr(vp, "_daily_rows_by_ticker", lambda: _rows(10_000, 10_050))  # only a 50 EUR gain

    row = vp.compute_for_year(2026)["rows"][0]

    assert row["vorabpauschale"] == 50.0  # capped below the 160.30 formula result
    assert row["taxable_amount"] == pytest.approx(35.0)  # 50 * 0.7


def test_distributions_reduce_the_actual_gain_cap(monkeypatch, one_etf):
    monkeypatch.setattr(vp, "basiszins_for_year", lambda y: 0.0229)
    monkeypatch.setattr(vp, "_daily_rows_by_ticker", lambda: _rows(10_000, 10_100))
    monkeypatch.setattr(vp, "_distributions_eur", lambda t, y: 30.0)

    row = vp.compute_for_year(2026)["rows"][0]

    assert row["vorabpauschale"] == pytest.approx(70.0)  # (10100-10000-30), still under the formula cap


def test_a_losing_year_caps_the_vorabpauschale_at_zero(monkeypatch, one_etf):
    monkeypatch.setattr(vp, "basiszins_for_year", lambda y: 0.0229)
    monkeypatch.setattr(vp, "_daily_rows_by_ticker", lambda: _rows(10_000, 9_000))

    row = vp.compute_for_year(2026)["rows"][0]

    assert row["vorabpauschale"] == 0.0 and row["taxable_amount"] == 0.0


def test_missing_basiszins_reports_manual_needed(monkeypatch, one_etf):
    monkeypatch.setattr(vp, "basiszins_for_year", lambda y: None)
    monkeypatch.setattr(vp, "_daily_rows_by_ticker", lambda: _rows(10_000, 10_800))

    row = vp.compute_for_year(2026)["rows"][0]

    assert row["confidence"] == "manual_needed" and row["vorabpauschale"] is None
    assert "basiszins.yaml" in row["note"]


def test_missing_price_history_reports_manual_needed(monkeypatch, one_etf):
    monkeypatch.setattr(vp, "basiszins_for_year", lambda y: 0.0229)
    monkeypatch.setattr(vp, "_daily_rows_by_ticker", lambda: {})

    row = vp.compute_for_year(2026)["rows"][0]

    assert row["confidence"] == "manual_needed" and row["vorabpauschale"] is None


def test_no_thesaurierend_etfs_is_an_empty_list_not_an_error(monkeypatch):
    monkeypatch.setattr(vp, "_thesaurierend_etf_tickers", lambda: [])
    out = vp.compute_for_year(2026)
    assert out["rows"] == [] and out["total_taxable_eur"] == 0.0


# --- config yaml readers ---------------------------------------------------------------------

def test_load_etf_metadata_parses_the_yaml(tmp_path, monkeypatch):
    monkeypatch.setattr(vp, "_etf_map_cache", None)
    monkeypatch.setattr(vp, "_etf_map_mtime", None)
    path = tmp_path / "etf_metadata.yaml"
    path.write_text("VWCE.DE:\n  type: thesaurierend\n  teilfreistellung: 0.3\n", encoding="utf-8")

    assert vp._load_etf_metadata(path) == {"VWCE.DE": {"type": "thesaurierend", "teilfreistellung": 0.3}}


def test_load_basiszins_parses_the_yaml(tmp_path, monkeypatch):
    monkeypatch.setattr(vp, "_basiszins_cache", None)
    monkeypatch.setattr(vp, "_basiszins_mtime", None)
    path = tmp_path / "basiszins.yaml"
    path.write_text("2024: 0.0229\n2025: 0.0253\n", encoding="utf-8")

    assert vp._load_basiszins(path) == {2024: 0.0229, 2025: 0.0253}


def test_etf_metadata_defaults_to_thesaurierend_equity_fund_when_unlisted(monkeypatch):
    monkeypatch.setattr(vp, "_load_etf_metadata", lambda: {"VWCE.DE": {"type": "ausschüttend", "teilfreistellung": 0.15}})
    assert vp.etf_metadata("CSPX.L") == {"type": "thesaurierend", "teilfreistellung": 0.30}
    assert vp.etf_metadata("VWCE.DE") == {"type": "ausschüttend", "teilfreistellung": 0.15}
