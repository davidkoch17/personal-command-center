"""Tests for modules/finance/cashflow.py's ledger CRUD + needs-review flow."""
from __future__ import annotations

from datetime import date

import pytest

from modules.finance import cashflow


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    """Redirect the ledger file to a throwaway path so tests never touch real data."""
    monkeypatch.setattr(cashflow, "CASHFLOW_TRANSACTIONS_FILE", tmp_path / "cashflow_transactions.jsonl")
    monkeypatch.setattr(cashflow, "CASHFLOW_RESERVE_BALANCE_FILE", tmp_path / "cashflow_reserve_balance.json")
    monkeypatch.setattr(cashflow, "CASHFLOW_RESERVE_TARGET_FILE", tmp_path / "cashflow_reserve_target.json")
    monkeypatch.setattr(cashflow, "CASHFLOW_ACCOUNTS_FILE", tmp_path / "cashflow_accounts.json")


def make_entry(**overrides) -> cashflow.CashflowEntry:
    fields = dict(
        date=date(2026, 7, 1),
        direction="expense",
        amount=12.5,
        category="Groceries",
        description="test entry",
    )
    fields.update(overrides)
    return cashflow.CashflowEntry(**fields)


def test_add_entries_appends_and_dedupes():
    e1 = make_entry()
    e2 = make_entry(description="second entry")
    result = cashflow.add_entries([e1, e2, e1])  # e1 repeated -> should dedupe

    assert result == {"added": 2, "skipped": 1}
    assert len(cashflow.list_entries()) == 2


def test_list_entries_sorted_by_date():
    late = make_entry(date=date(2026, 7, 20), description="late")
    early = make_entry(date=date(2026, 7, 1), description="early")
    cashflow.add_entries([late, early])

    entries = cashflow.list_entries()
    assert [e.description for e in entries] == ["early", "late"]


def test_list_entries_empty_when_no_file():
    assert cashflow.list_entries() == []


def test_needs_review_entries_filters_flagged_only():
    flagged = make_entry(description="flagged", needs_review=True, question="which category?")
    clean = make_entry(description="clean", needs_review=False)
    cashflow.add_entries([flagged, clean])

    review = cashflow.needs_review_entries()
    assert [e.description for e in review] == ["flagged"]


def test_question_type_defaults_to_freetext():
    e = make_entry()
    assert e.question_type == "freetext"


def test_question_type_category_round_trips_through_ledger():
    e = make_entry(needs_review=True, question="which category?", question_type="category")
    cashflow.add_entries([e])

    [stored] = cashflow.needs_review_entries()
    assert stored.question_type == "category"


def test_resolve_entry_applies_fields_and_clears_review_flag():
    e = make_entry(category="Uncategorized", needs_review=True, question="which category?", question_type="category")
    cashflow.add_entries([e])

    updated = cashflow.resolve_entry(e.id, category="Groceries")

    assert updated is not None
    assert updated.category == "Groceries"
    assert updated.needs_review is False
    assert cashflow.needs_review_entries() == []


def test_resolve_entry_unknown_id_returns_none():
    assert cashflow.resolve_entry("does-not-exist", category="Groceries") is None


def test_clear_all_deletes_every_entry():
    cashflow.add_entries([make_entry(), make_entry(description="second")])
    assert len(cashflow.list_entries()) == 2

    removed = cashflow.clear_all()

    assert removed == 2
    assert cashflow.list_entries() == []


# --- Reserve target override --------------------------------------------------

def test_get_reserve_target_defaults_to_notgroschen_target():
    assert cashflow.get_reserve_target() == cashflow.NOTGROSCHEN_TARGET


def test_set_reserve_target_overrides_default():
    cashflow.set_reserve_target(5000)
    assert cashflow.get_reserve_target() == 5000


# --- Accounts (where cash sits) ------------------------------------------------

def test_list_accounts_empty_when_no_file():
    assert cashflow.list_accounts() == []


def test_set_account_adds_new_account():
    cashflow.set_account("Haspa Giro", 1200.0)

    assert cashflow.list_accounts() == [{"name": "Haspa Giro", "balance": 1200.0, "is_reserve": False}]


def test_set_account_updates_existing_by_name():
    cashflow.set_account("Haspa Giro", 1200.0)
    cashflow.set_account("Haspa Giro", 1500.0)

    accounts = cashflow.list_accounts()
    assert len(accounts) == 1
    assert accounts[0]["balance"] == 1500.0


def test_set_account_reserve_flag_is_exclusive():
    cashflow.set_account("Haspa Giro", 1200.0, is_reserve=True)
    cashflow.set_account("Tagesgeld", 2000.0, is_reserve=True)

    accounts = {a["name"]: a["is_reserve"] for a in cashflow.list_accounts()}
    assert accounts == {"Haspa Giro": False, "Tagesgeld": True}


def test_delete_account_removes_by_name():
    cashflow.set_account("Haspa Giro", 1200.0)
    cashflow.set_account("Tagesgeld", 2000.0)

    remaining = cashflow.delete_account("Haspa Giro")

    assert [a["name"] for a in remaining] == ["Tagesgeld"]


def test_accounts_summary_totals_balances():
    cashflow.set_account("Haspa Giro", 1200.0)
    cashflow.set_account("Tagesgeld", 2000.0, is_reserve=True)

    summary = cashflow.accounts_summary()

    assert summary["total_cash"] == 3200.0
    assert len(summary["accounts"]) == 2


# --- Overview tab aggregation --------------------------------------------------

def month_entries(month: str, income: float, expenses: float) -> list[cashflow.CashflowEntry]:
    d = date.fromisoformat(f"{month}-05")
    out = []
    if income:
        out.append(make_entry(date=d, direction="income", amount=income, category="Salary"))
    if expenses:
        out.append(make_entry(date=d, direction="expense", amount=expenses, category="Groceries"))
    return out


def test_trailing_avg_and_delta_none_below_full_window():
    cashflow.add_entries(month_entries("2026-06", 1000, 500))
    avg, delta = cashflow._trailing_avg_and_delta("2026-07", 1200, "income_total")
    assert (avg, delta) == (None, None)


def test_trailing_avg_and_delta_computed_with_full_window():
    for m, income in [("2026-04", 1000), ("2026-05", 1000), ("2026-06", 1000)]:
        cashflow.add_entries(month_entries(m, income, 0))
    avg, delta = cashflow._trailing_avg_and_delta("2026-07", 1100, "income_total")
    assert avg == 1000
    assert delta == 10.0


def test_guarded_savings_rate_none_below_min_income():
    assert cashflow.guarded_savings_rate(50, 20) is None


def test_guarded_savings_rate_computed_above_min_income():
    assert cashflow.guarded_savings_rate(1000, 250) == 0.25


def test_top_categories_ranks_and_shares_total():
    cashflow.add_entries([
        make_entry(direction="expense", amount=300, category="Rent"),
        make_entry(direction="expense", amount=100, category="Groceries"),
        make_entry(direction="expense", amount=50, category="Transport"),
        make_entry(direction="expense", amount=50, category="Health"),
    ])
    top = cashflow.top_categories("2026-07", n=3)
    assert [c["category"] for c in top] == ["Rent", "Groceries", "Transport"]
    assert top[0]["percent_of_total"] == 60.0  # 300 / 500


def test_biggest_mover_none_below_full_window():
    cashflow.add_entries(month_entries("2026-06", 0, 100))
    assert cashflow.biggest_mover("2026-07") is None


def test_biggest_mover_picks_largest_percent_increase():
    for m in ("2026-04", "2026-05", "2026-06"):
        cashflow.add_entries([
            make_entry(date=date.fromisoformat(f"{m}-05"), direction="expense", amount=100, category="Groceries"),
            make_entry(date=date.fromisoformat(f"{m}-05"), direction="expense", amount=100, category="Travel"),
        ])
    cashflow.add_entries([
        make_entry(date=date(2026, 7, 5), direction="expense", amount=110, category="Groceries"),  # +10%
        make_entry(date=date(2026, 7, 5), direction="expense", amount=200, category="Travel"),  # +100%
    ])
    mover = cashflow.biggest_mover("2026-07")
    assert mover == {"category": "Travel", "delta_percent": 100.0}


def test_overview_shape_and_reserve_split_included():
    for m in ("2026-04", "2026-05", "2026-06"):
        cashflow.add_entries(month_entries(m, 2000, 1000))
    cashflow.add_entries(month_entries("2026-07", 2000, 1000))
    cashflow.set_reserve_balance("2026-07", 500)

    data = cashflow.overview("2026-07")

    assert data["month"] == "2026-07"
    assert data["income"] == {"total": 2000.0, "avg_3mo": 2000.0, "delta_percent": 0.0}
    assert data["savings_rate"] == pytest.approx(0.5)
    assert data["runway_months"] is None
    assert data["reserve"]["reserve_balance"] == 500
    assert "to_reserve" in data["split_recommendation"]
    assert data["top_categories"][0]["category"] == "Groceries"


# --- Alerts engine (Phase 10) -----------------------------------------------

def test_category_spike_alert_fires_above_2x_average():
    for m in ("2026-04", "2026-05", "2026-06"):
        cashflow.add_entries([
            make_entry(date=date.fromisoformat(f"{m}-05"), direction="expense", amount=100, category="Dining"),
        ])
    cashflow.add_entries([
        make_entry(date=date(2026, 7, 5), direction="expense", amount=250, category="Dining"),  # 2.5x avg
    ])
    alerts = cashflow.alerts("2026-07")
    spikes = [a for a in alerts if a["type"] == "category_spike"]
    assert len(spikes) == 1
    assert spikes[0]["severity"] == "medium"
    assert spikes[0]["tab"] == "spending"


def test_no_category_spike_alert_below_threshold():
    for m in ("2026-04", "2026-05", "2026-06"):
        cashflow.add_entries([
            make_entry(date=date.fromisoformat(f"{m}-05"), direction="expense", amount=100, category="Dining"),
        ])
    cashflow.add_entries([
        make_entry(date=date(2026, 7, 5), direction="expense", amount=150, category="Dining"),  # +50%, below 2x
    ])
    alerts = cashflow.alerts("2026-07")
    assert not [a for a in alerts if a["type"] == "category_spike"]


def test_new_recurring_alert_fires_on_threshold_crossing_month():
    cashflow.add_entries([
        make_entry(date=date(2026, 6, 1), direction="expense", amount=15.99, category="Subscriptions", description="Netflix"),
        make_entry(date=date(2026, 7, 1), direction="expense", amount=15.99, category="Subscriptions", description="Netflix"),
    ])
    alerts = cashflow.alerts("2026-07")
    new_recurring = [a for a in alerts if a["type"] == "new_recurring"]
    assert len(new_recurring) == 1
    assert "Netflix" in new_recurring[0]["message"]


def test_price_creep_alert_fires_on_rise():
    cashflow.add_entries([
        make_entry(date=date(2026, 5, 1), direction="expense", amount=10.0, category="Subscriptions", description="Spotify"),
        make_entry(date=date(2026, 6, 1), direction="expense", amount=10.0, category="Subscriptions", description="Spotify"),
        make_entry(date=date(2026, 7, 1), direction="expense", amount=12.0, category="Subscriptions", description="Spotify"),
    ])
    alerts = cashflow.alerts("2026-07")
    assert [a for a in alerts if a["type"] == "price_creep"]


def test_reserve_full_alert_fires_only_on_crossing_month():
    cashflow.set_reserve_balance("2026-06", 3000)
    cashflow.set_reserve_balance("2026-07", 4000)
    cashflow.add_entries(month_entries("2026-07", 0, 0))

    alerts_july = cashflow.alerts("2026-07")
    assert [a for a in alerts_july if a["type"] == "reserve_full"]

    cashflow.set_reserve_balance("2026-08", 4200)
    cashflow.add_entries(month_entries("2026-08", 0, 0))
    alerts_august = cashflow.alerts("2026-08")
    assert not [a for a in alerts_august if a["type"] == "reserve_full"]


def test_reserve_near_full_alert_fires_within_threshold():
    cashflow.set_reserve_balance("2026-07", 3700)
    cashflow.add_entries(month_entries("2026-07", 0, 0))
    alerts = cashflow.alerts("2026-07")
    near_full = [a for a in alerts if a["type"] == "reserve_near_full"]
    assert len(near_full) == 1
    assert "€300" in near_full[0]["message"]


def test_low_runway_alert_only_fires_for_latest_month():
    cashflow.set_account("Giro", 500)
    for m in ("2026-05", "2026-06", "2026-07"):
        cashflow.add_entries(month_entries(m, 0, 2000))

    alerts_latest = cashflow.alerts("2026-07")
    assert [a for a in alerts_latest if a["type"] == "low_runway"]

    alerts_older = cashflow.alerts("2026-06")
    assert not [a for a in alerts_older if a["type"] == "low_runway"]


def test_alerts_sorted_by_severity_and_have_stable_ids():
    cashflow.set_account("Giro", 500)
    for m in ("2026-05", "2026-06", "2026-07"):
        cashflow.add_entries(month_entries(m, 0, 2000))
    alerts = cashflow.alerts("2026-07")
    ranks = [{"high": 0, "medium": 1, "low": 2}[a["severity"]] for a in alerts]
    assert ranks == sorted(ranks)
    assert len({a["id"] for a in alerts}) == len(alerts)


def test_alerts_empty_when_nothing_flagged():
    cashflow.set_account("Giro", 50000)  # ample runway so it can't trip the runway alert
    cashflow.add_entries(month_entries("2026-07", 2000, 500))
    assert cashflow.alerts("2026-07") == []
