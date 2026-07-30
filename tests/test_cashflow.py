"""Tests for modules/finance/cashflow.py's ledger CRUD + needs-review flow."""
from __future__ import annotations

from datetime import date

import pytest

from modules.finance import cashflow


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    """Redirect the ledger file to a throwaway path so tests never touch real data."""
    monkeypatch.setattr(cashflow, "CASHFLOW_TRANSACTIONS_FILE", tmp_path / "cashflow_transactions.jsonl")


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
