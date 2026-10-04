"""Tests for modules/finance/networth.py (Chunk 9.7 — Net Worth pillar).

Pure-function inputs (accounts / holdings / prices) via monkeypatch — no
network, no real ledger, no price cache.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import networth as networth_api
from modules.finance import networth


@pytest.fixture(autouse=True)
def no_disk(monkeypatch):
    """Every test sets its own accounts/holdings/prices via monkeypatch;
    nothing should fall through to the real cashflow ledger, positions.json
    or price cache. monkeypatch.setattr (not raw assignment) on every name a
    test might later re-patch, so teardown always restores the true original —
    even when a test overrides one of these again mid-body."""
    monkeypatch.setattr(networth.cashflow, "list_accounts", lambda: [])
    monkeypatch.setattr(networth, "current_holdings", lambda: {})
    monkeypatch.setattr(networth, "get_position", lambda t: None)
    monkeypatch.setattr(networth, "cost_basis", lambda t: (0.0, 0.0))
    monkeypatch.setattr(networth, "resolve_bucket", lambda t: "etf_foundation")
    monkeypatch.setattr(networth, "latest_price_eur", lambda t: None)
    monkeypatch.setattr(networth, "read_rows", lambda path: [])
    monkeypatch.setattr(networth, "get_closes", lambda t: pd.Series(dtype="float64"))


def _lp(eur_price: float):
    return type("LP", (), {"eur_price": eur_price})()


# --- compute_breakdown -------------------------------------------------------

def test_breakdown_sums_to_total(monkeypatch):
    monkeypatch.setattr(networth.cashflow, "list_accounts", lambda: [
        {"name": "Haspa Girokonto", "balance": 1000.0, "is_reserve": False},
        {"name": "Trade Republic Cash", "balance": 500.0, "is_reserve": False},
    ])
    monkeypatch.setattr(networth, "current_holdings", lambda: {"AAA": 2.0, "BBB": 3.0})
    monkeypatch.setattr(networth, "resolve_bucket", lambda t: {"AAA": "etf_foundation", "BBB": "crypto"}[t])
    monkeypatch.setattr(networth, "latest_price_eur", lambda t: _lp({"AAA": 100.0, "BBB": 50.0}[t]))

    result = networth.compute_breakdown()
    assert result["bank_cash"] == 1000.0
    assert result["brokerage_cash"] == 500.0
    assert result["etfs"] == 200.0    # AAA: 2.0 * 100.0
    assert result["crypto"] == 150.0  # BBB: 3.0 * 50.0
    assert result["total"] == 1000.0 + 500.0 + 200.0 + 150.0


def test_empty_portfolio_renders_cash_only(monkeypatch):
    monkeypatch.setattr(networth.cashflow, "list_accounts", lambda: [
        {"name": "Haspa Girokonto", "balance": 1091.18, "is_reserve": False},
    ])
    # current_holdings / resolve_bucket / latest_price_eur stay the no_disk empty defaults.

    result = networth.compute_breakdown()
    assert result["bank_cash"] == 1091.18
    assert result["etfs"] == result["single_stocks"] == result["crypto"] == result["wild_cards"] == 0.0
    assert result["total"] == 1091.18


def test_liabilities_subtract_from_total(monkeypatch):
    monkeypatch.setattr(networth.cashflow, "list_accounts", lambda: [
        {"name": "Haspa Girokonto", "balance": 1000.0, "is_reserve": False},
        {"name": "Car Loan", "balance": 300.0, "is_reserve": False},
    ])

    result = networth.compute_breakdown()
    assert result["liabilities"] == 300.0
    assert result["total"] == 1000.0 - 300.0


# --- compute_milestone_projection -------------------------------------------

def _nw_row(days_ago: int, value: float) -> dict:
    return {"date": (date.today() - timedelta(days=days_ago)).isoformat(), "net_worth_eur": str(value)}


def test_milestone_projection_positive_trend(monkeypatch):
    monkeypatch.setattr(networth.cashflow, "list_accounts", lambda: [
        {"name": "Haspa Girokonto", "balance": 6000.0, "is_reserve": False},
    ])
    monkeypatch.setattr(networth, "read_rows", lambda path: [_nw_row(95, 3000.0), _nw_row(1, 6000.0)])

    result = networth.compute_milestone_projection(target_eur=25000.0)
    assert result["status"] == "on_track"
    assert result["monthly_rate"] == pytest.approx((6000.0 - 3000.0) / 3)
    assert result["months_to_goal"] is not None
    assert result["projected_date"] is not None


def test_milestone_projection_flat_trend(monkeypatch):
    monkeypatch.setattr(networth.cashflow, "list_accounts", lambda: [
        {"name": "Haspa Girokonto", "balance": 6000.0, "is_reserve": False},
    ])
    monkeypatch.setattr(networth, "read_rows", lambda path: [_nw_row(95, 7000.0), _nw_row(1, 6000.0)])  # declining

    result = networth.compute_milestone_projection(target_eur=25000.0)
    assert result["status"] == "paused"
    assert result["monthly_rate"] < 0
    assert result["months_to_goal"] is None
    assert result["projected_date"] is None


def test_milestone_already_reached(monkeypatch):
    monkeypatch.setattr(networth.cashflow, "list_accounts", lambda: [
        {"name": "Haspa Girokonto", "balance": 30000.0, "is_reserve": False},
    ])

    result = networth.compute_milestone_projection(target_eur=25000.0)
    assert result["status"] == "reached"
    assert result["pct"] == 100.0
    assert result["months_to_goal"] is None


def test_milestone_insufficient_history(monkeypatch):
    monkeypatch.setattr(networth.cashflow, "list_accounts", lambda: [
        {"name": "Haspa Girokonto", "balance": 6000.0, "is_reserve": False},
    ])
    monkeypatch.setattr(networth, "read_rows", lambda path: [_nw_row(5, 5000.0)])  # only 5 days of history

    result = networth.compute_milestone_projection(target_eur=25000.0)
    assert result["status"] == "insufficient_history"


# --- compute_accounts_hierarchy ---------------------------------------------

def test_accounts_hierarchy_structure(monkeypatch):
    monkeypatch.setattr(networth.cashflow, "list_accounts", lambda: [
        {"name": "Haspa Girokonto", "balance": 1091.18, "is_reserve": False},
        {"name": "Trade Republic Cash", "balance": 4381.96, "is_reserve": False},
    ])
    monkeypatch.setattr(networth, "current_holdings", lambda: {"VWCE.DE": 4.375729})
    monkeypatch.setattr(networth, "latest_price_eur", lambda t: _lp(171.14))
    monkeypatch.setattr(networth, "cost_basis", lambda t: (171.40, 750.0))
    # get_closes stays the no_disk empty default -> pct_change naturally returns None.

    result = networth.compute_accounts_hierarchy()
    assert result["cash"]["total"] == pytest.approx(1091.18 + 4381.96)
    assert {a["name"] for a in result["cash"]["accounts"]} == {"Haspa Girokonto", "Trade Republic Cash"}
    assert result["portfolio"]["total"] == pytest.approx(4.375729 * 171.14, abs=0.01)
    holding = result["portfolio"]["holdings"][0]
    assert holding["ticker"] == "VWCE.DE"
    assert holding["gain"] == pytest.approx(4.375729 * 171.14 - 750.0, abs=0.01)
    assert holding["pct_1m"] is None and holding["pct_1y"] is None


# --- pct_change ---------------------------------------------------------------

def _closes(start: date, days: int, start_price: float, end_price: float) -> pd.Series:
    """A short, linear daily-close series — just long enough (or not) to
    exercise pct_change's history-depth check."""
    idx = pd.date_range(start, periods=days, freq="D")
    values = [start_price + (end_price - start_price) * i / max(days - 1, 1) for i in range(days)]
    return pd.Series(values, index=idx)


def test_1m_percent_insufficient_history_returns_none(monkeypatch):
    today = date(2026, 10, 4)
    # Only 10 days of cached price history -> can't look back 30 days.
    monkeypatch.setattr(networth, "get_closes", lambda t: _closes(today - timedelta(days=9), 10, 100.0, 110.0))

    assert networth.pct_change("NEWLISTING", 30, on=today) is None


def test_1y_percent_insufficient_history_returns_none(monkeypatch):
    today = date(2026, 10, 4)
    # 200 days of history -> enough for 1M, not enough for 1Y (365).
    monkeypatch.setattr(networth, "get_closes", lambda t: _closes(today - timedelta(days=199), 200, 100.0, 120.0))

    assert networth.pct_change("YOUNGTICKER", 30, on=today) is not None
    assert networth.pct_change("YOUNGTICKER", 365, on=today) is None


# --- endpoint smoke test ------------------------------------------------------

def test_snapshot_endpoint_smoke(monkeypatch):
    monkeypatch.setattr(networth.cashflow, "list_accounts", lambda: [
        {"name": "Haspa Girokonto", "balance": 1091.18, "is_reserve": False},
    ])

    app = FastAPI()
    app.include_router(networth_api.router, prefix="/api/finance")
    client = TestClient(app)

    resp = client.get("/api/finance/networth/snapshot", params={"period": "3M"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"breakdown", "delta_this_month", "trend", "milestone", "accounts", "bucket_labels"}
    assert body["breakdown"]["bank_cash"] == 1091.18


def test_snapshot_endpoint_rejects_bad_period():
    app = FastAPI()
    app.include_router(networth_api.router, prefix="/api/finance")
    client = TestClient(app)

    resp = client.get("/api/finance/networth/snapshot", params={"period": "5Y"})
    assert resp.status_code == 422
