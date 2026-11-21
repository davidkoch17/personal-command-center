"""Cash source for the daily snapshot / backfill (bank_total no longer 0 when
the Excel Bank sheet is empty). No disk, no network: everything monkeypatched."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from modules.finance import backfill, cashflow, daily_snapshot


ACCOUNTS = [
    {"name": "Haspa Girokonto", "balance": 61.08, "is_reserve": False},
    {"name": "Trade Republic Cash", "balance": 10.0, "is_reserve": False},
    {"name": "Car Loan", "balance": 500.0, "is_reserve": False},
]


@pytest.fixture
def accounts(monkeypatch):
    monkeypatch.setattr(cashflow, "list_accounts", lambda: ACCOUNTS)
    monkeypatch.setattr(daily_snapshot, "bank_month_history", lambda: {})


def test_today_uses_account_balances(accounts):
    assert daily_snapshot.bank_total_asof(date.today()) == pytest.approx(71.08)
    assert daily_snapshot.debts_total_asof(date.today()) == pytest.approx(500.0)


def test_past_date_without_sheet_history_is_zero(accounts):
    past = date.today() - timedelta(days=10)
    assert daily_snapshot.bank_total_asof(past) == 0.0
    assert daily_snapshot.debts_total_asof(past) == 0.0


def test_sheet_history_still_used_for_past_dates(monkeypatch):
    monkeypatch.setattr(cashflow, "list_accounts", lambda: ACCOUNTS)
    monkeypatch.setattr(daily_snapshot, "bank_month_history", lambda: {"2026-01": 1234.0})
    assert daily_snapshot.bank_total_asof(date(2026, 2, 15)) == 1234.0


def test_no_accounts_falls_back_to_sheet(monkeypatch):
    monkeypatch.setattr(cashflow, "list_accounts", lambda: [])
    monkeypatch.setattr(daily_snapshot, "bank_month_history", lambda: {"2026-01": 99.0})
    assert daily_snapshot.bank_total_asof(date.today()) == 99.0


def test_backfill_keeps_recorded_bank_for_past_days(accounts, monkeypatch):
    past = (date.today() - timedelta(days=3)).isoformat()
    today = date.today().isoformat()
    pos_rows = [
        {"date": past, "ticker": "AAA", "value_eur": "100"},
        {"date": today, "ticker": "AAA", "value_eur": "110"},
    ]
    recorded = [{"date": past, "bank_total": "42.5", "debts_total": "0"}]
    written: list[dict] = []

    def fake_read(path):
        return pos_rows if path == backfill.POSITIONS_DAILY_CSV else recorded

    monkeypatch.setattr(backfill, "read_rows", fake_read)
    monkeypatch.setattr(backfill, "get_position", lambda t: None)
    monkeypatch.setattr(backfill, "upsert_rows", lambda path, rows, *a, **k: written.extend(rows))

    rows = {r["date"]: r for r in backfill.backfill_networth()}
    assert rows[past]["bank_total"] == 42.5
    assert rows[past]["net_worth_eur"] == 142.5
    assert rows[today]["bank_total"] == pytest.approx(71.08)
    assert rows[today]["debts_total"] == pytest.approx(500.0)
    assert rows[today]["net_worth_eur"] == pytest.approx(110 + 71.08 - 500)
    assert len(written) == 2
