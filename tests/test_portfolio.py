"""Tests for modules/finance/positions.py's transaction ledger CRUD."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from modules.finance import positions, risk


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    """Redirect the transactions/positions files to throwaway paths."""
    monkeypatch.setattr(positions, "TRANSACTIONS_FILE", tmp_path / "transactions.jsonl")
    monkeypatch.setattr(positions, "POSITIONS_FILE", tmp_path / "positions.json")


def make_txn(**overrides) -> positions.Transaction:
    fields = dict(
        date=date(2026, 7, 1),
        ticker="VWCE",
        action="buy",
        quantity=10.0,
        price=100.0,
        currency="EUR",
    )
    fields.update(overrides)
    return positions.Transaction(**fields)


def test_record_and_list_transactions():
    t = make_txn()
    positions.record_transaction(t)

    txns = positions.list_transactions()
    assert len(txns) == 1
    assert txns[0].id == t.id
    assert txns[0].ticker == "VWCE"


def test_list_transactions_empty_when_no_file():
    assert positions.list_transactions() == []


def test_update_transaction_applies_partial_fields():
    t = make_txn(quantity=10.0, price=100.0)
    positions.record_transaction(t)

    updated = positions.update_transaction(t.id, quantity=15.0)

    assert updated is not None
    assert updated.quantity == 15.0
    assert updated.price == 100.0  # untouched fields keep their value
    assert updated.id == t.id


def test_update_transaction_unknown_id_returns_none():
    assert positions.update_transaction("does-not-exist", quantity=5.0) is None


def test_delete_transaction_removes_row():
    t1 = make_txn()
    t2 = make_txn(ticker="AAPL")
    positions.record_transaction(t1)
    positions.record_transaction(t2)

    removed = positions.delete_transaction(t1.id)

    assert removed is True
    remaining = positions.list_transactions()
    assert len(remaining) == 1
    assert remaining[0].id == t2.id


def test_delete_transaction_unknown_id_returns_false():
    assert positions.delete_transaction("does-not-exist") is False


def test_current_holdings_nets_buys_and_sells():
    positions.record_transaction(make_txn(action="buy", quantity=10.0))
    positions.record_transaction(make_txn(action="sell", quantity=4.0))

    holdings = positions.current_holdings()
    assert holdings == {"VWCE": 6.0}


def test_current_holdings_drops_zeroed_positions():
    positions.record_transaction(make_txn(action="buy", quantity=10.0))
    positions.record_transaction(make_txn(action="sell", quantity=10.0))

    assert positions.current_holdings() == {}


def test_cost_basis_fifo_after_partial_sell():
    positions.record_transaction(make_txn(action="buy", quantity=10.0, price=100.0))
    positions.record_transaction(make_txn(action="buy", quantity=10.0, price=120.0, date=date(2026, 7, 2)))
    positions.record_transaction(make_txn(action="sell", quantity=10.0, date=date(2026, 7, 3)))

    avg_cost, total_basis = positions.cost_basis("VWCE")

    # First (cheaper) lot fully consumed by the sell; only the 120/share lot remains.
    assert avg_cost == 120.0
    assert total_basis == 1200.0


def test_add_and_get_position():
    p = positions.Position(ticker="vwce", name="Vanguard All-World", type="etf", bucket="etf_foundation")
    positions.add_position(p)

    found = positions.get_position("VWCE")  # case-insensitive lookup
    assert found is not None
    assert found.name == "Vanguard All-World"


def test_beta_vs_uses_the_requested_benchmark_ticker(monkeypatch):
    """Per-holding beta (GET /api/finance/holdings) used to hardcode ^GSPC — Item
    A2 wires it to whichever benchmark the Risk tab's dropdown resolves to. This
    guards the underlying mechanism: beta_vs must key off its ``benchmark_ticker``
    argument, not a fixed name, so two different benchmarks yield different betas.
    """
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    portfolio_returns = pd.Series([0.01, -0.02] * 15, index=dates)

    def fake_get_returns(ticker):
        # MSCI World (URTH) moves at half the portfolio's swing; S&P 500 (^GSPC)
        # moves at double it — deterministic, no network/price-cache needed.
        if ticker == "URTH":
            return pd.Series([0.005, -0.01] * 15, index=dates)
        if ticker == "^GSPC":
            return pd.Series([0.02, -0.04] * 15, index=dates)
        return pd.Series(dtype=float)

    monkeypatch.setattr(risk, "get_returns", fake_get_returns)

    beta_msci = risk.beta_vs(portfolio_returns, "URTH")
    beta_sp500 = risk.beta_vs(portfolio_returns, "^GSPC")

    assert beta_msci is not None
    assert beta_sp500 is not None
    assert beta_msci != beta_sp500
    assert round(beta_msci, 4) == 2.0
    assert round(beta_sp500, 4) == 0.5
