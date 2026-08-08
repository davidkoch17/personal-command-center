"""Tests for modules/finance/period_pnl.py's networth_bridge (Phase 9)."""
from __future__ import annotations

from datetime import date

import pytest

from modules.finance import cashflow, period_pnl, positions


NW_COLUMNS = ["date", "bank_total", "portfolio_total_eur", "crypto_total_eur", "debts_total", "net_worth_eur"]


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Redirect the daily net-worth CSV + transaction ledger to throwaway paths."""
    monkeypatch.setattr(period_pnl, "NETWORTH_DAILY_CSV", tmp_path / "networth_daily.csv")
    monkeypatch.setattr(positions, "TRANSACTIONS_FILE", tmp_path / "transactions.jsonl")
    monkeypatch.setattr(positions, "POSITIONS_FILE", tmp_path / "positions.json")


def _seed_networth_daily(rows: list[dict]) -> None:
    from modules.finance._csv_store import write_rows

    write_rows(period_pnl.NETWORTH_DAILY_CSV, rows, NW_COLUMNS)


def make_txn(**overrides) -> positions.Transaction:
    fields = dict(date=date(2026, 6, 15), ticker="VWCE", action="buy", quantity=1.0, price=100.0, currency="EUR")
    fields.update(overrides)
    return positions.Transaction(**fields)


def test_unavailable_when_no_history():
    result = period_pnl.networth_bridge("2026-06")
    assert result == {"available": False, "reason": "no networth_daily.csv history yet", "month": "2026-06"}


def test_unavailable_when_month_not_covered():
    _seed_networth_daily([
        {"date": "2026-07-15", "bank_total": 1000, "portfolio_total_eur": 0, "crypto_total_eur": 0,
         "debts_total": 0, "net_worth_eur": 1000},
    ])
    result = period_pnl.networth_bridge("2026-06")
    assert result["available"] is False
    assert "2026-06" in result["reason"]


def test_bridge_reconciles_with_income_expenses(monkeypatch):
    _seed_networth_daily([
        {"date": "2026-05-31", "bank_total": 10000, "portfolio_total_eur": 5000, "crypto_total_eur": 0,
         "debts_total": 0, "net_worth_eur": 15000},
        {"date": "2026-06-30", "bank_total": 10500, "portfolio_total_eur": 5300, "crypto_total_eur": 0,
         "debts_total": 0, "net_worth_eur": 15800},
    ])
    # +300 contributed into the depot mid-June, on top of whatever the market did.
    positions.record_transaction(make_txn(action="buy", quantity=3.0, price=100.0, date=date(2026, 6, 10)))

    monkeypatch.setattr(cashflow, "available_months", lambda: ["2026-06"])
    monkeypatch.setattr(
        cashflow, "monthly_summary",
        lambda m: {"income_total": 3000.0, "expenses_total": 2500.0} if m == "2026-06" else {},
    )

    result = period_pnl.networth_bridge("2026-06")

    assert result["available"] is True
    assert result["opening_net_worth"] == 15000
    assert result["closing_net_worth"] == 15800
    assert result["mom_delta"] == 800
    assert result["income"] == 3000.0
    assert result["expenses"] == 2500.0
    assert result["savings"] == 500.0
    assert result["contributions"] == 300.0
    # invest_delta (5300-5000=300) - contributions (300) = 0 price-driven P&L.
    assert result["market_pnl"] == 0.0
    # income - expenses + contributions + market_pnl = 500 + 300 + 0 = 800 == mom_delta -> no residual.
    assert result["residual"] == 0.0


def test_bridge_derives_savings_when_cashflow_month_missing(monkeypatch):
    _seed_networth_daily([
        {"date": "2026-05-31", "bank_total": 10000, "portfolio_total_eur": 5000, "crypto_total_eur": 0,
         "debts_total": 0, "net_worth_eur": 15000},
        {"date": "2026-06-30", "bank_total": 10500, "portfolio_total_eur": 5300, "crypto_total_eur": 0,
         "debts_total": 0, "net_worth_eur": 15800},
    ])
    monkeypatch.setattr(cashflow, "available_months", lambda: [])

    result = period_pnl.networth_bridge("2026-06")

    assert result["available"] is True
    assert result["income"] is None
    assert result["expenses"] is None
    # mom_delta (800) - contributions (0, no ledger txns in this test) - market_pnl (300) = 500.
    assert result["savings"] == 500.0
    assert result["savings_source"].startswith("derived")
    assert result["residual"] == 0.0
