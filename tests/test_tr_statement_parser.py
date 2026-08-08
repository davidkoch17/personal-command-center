"""Tests for the TR statement parser's transaction-history reconciliation path.

David's real "account statement" export is a Kontoauszug (transaction log +
cash overview) with no Depotübersicht/holdings-table section — see the module
docstring in tr_statement_parser.py for the full diagnosis. These tests cover
the trade-replay fallback in reconcile_holdings(), which is what actually
fixes the "Alphabet still shows as held" bug: a fully-sold ticker must drop
out of the ledger (and, via _synthesize_holdings, out of the Investments_TR
sheet) even though the statement never provides a holdings snapshot to diff
against.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from modules.finance import positions
from modules.finance.tr_statement_parser import (
    ParsedStatement,
    Trade,
    _month_num,
    _parse_as_of_date,
    _TRADE_ROW_RE,
    reconcile_holdings,
)


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(positions, "TRANSACTIONS_FILE", tmp_path / "transactions.jsonl")
    monkeypatch.setattr(positions, "POSITIONS_FILE", tmp_path / "positions.json")


def make_statement(trades: list[Trade], as_of: date = date(2026, 7, 18)) -> ParsedStatement:
    return ParsedStatement(source_file=Path(__file__), as_of_date=as_of, trades=trades)


def sell(ticker: str, qty: float, amount: float | None = None, d: date = date(2026, 6, 10)) -> Trade:
    return Trade(date=d, isin="US02079K3059", name="ALPHABET INC.CL.A DL-,001", ticker=ticker,
                 action="sell", quantity=qty, amount=amount)


def buy(ticker: str, qty: float, amount: float | None = None, d: date = date(2026, 6, 10)) -> Trade:
    return Trade(date=d, isin="US02079K3059", name="ALPHABET INC.CL.A DL-,001", ticker=ticker,
                  action="buy", quantity=qty, amount=amount)


# --- reconcile_holdings: trade-history fallback path -------------------------

def test_fully_sold_position_drops_out_of_ledger():
    """The core bug: a closing sell with no matching holdings-table row must zero the ticker."""
    positions.record_transaction(positions.Transaction(
        date=date(2026, 1, 1), ticker="GOOGL", action="buy", quantity=10.0, price=150.0, currency="EUR",
    ))

    statement = make_statement([sell("GOOGL", 10.0, amount=2000.0)])
    result = reconcile_holdings(statement)

    assert result["applied"] is True
    assert "GOOGL" not in positions.current_holdings()
    assert statement.holdings == []  # synthesized snapshot has nothing left to show


def test_partial_sell_leaves_remainder():
    positions.record_transaction(positions.Transaction(
        date=date(2026, 1, 1), ticker="GOOGL", action="buy", quantity=10.0, price=150.0, currency="EUR",
    ))

    statement = make_statement([sell("GOOGL", 4.0, amount=800.0)])
    reconcile_holdings(statement)

    assert positions.current_holdings()["GOOGL"] == pytest.approx(6.0)


def test_sell_with_no_recorded_buy_clamps_to_zero_not_negative():
    """A statement can prove a sell happened even when the ledger never recorded the buy
    (e.g. ledger was never backfilled). Current holdings must never go negative."""
    statement = make_statement([sell("GOOGL", 3.425125, amount=915.85)])
    result = reconcile_holdings(statement)

    assert "GOOGL" in result["clamped_to_zero"]
    assert "GOOGL" not in positions.current_holdings()


def test_rerunning_same_statement_is_idempotent():
    positions.record_transaction(positions.Transaction(
        date=date(2026, 1, 1), ticker="GOOGL", action="buy", quantity=10.0, price=150.0, currency="EUR",
    ))
    statement = make_statement([sell("GOOGL", 10.0, amount=2000.0)])

    reconcile_holdings(statement)
    second = reconcile_holdings(make_statement([sell("GOOGL", 10.0, amount=2000.0)]))

    assert second["adjustments"] == []


def test_buy_trade_increases_holding():
    statement = make_statement([buy("GOOGL", 5.0, amount=1000.0)])
    reconcile_holdings(statement)

    assert positions.current_holdings()["GOOGL"] == pytest.approx(5.0)


def test_multiple_fills_same_ticker_net_correctly():
    """Mirrors the real statement: several partial sells for the same ticker on one day."""
    statement = make_statement([
        sell("GOOGL", 0.434782, amount=104.09),
        sell("GOOGL", 5.0, amount=1196.21),
        sell("GOOGL", 1.0, amount=275.15),
    ])
    positions.record_transaction(positions.Transaction(
        date=date(2026, 1, 1), ticker="GOOGL", action="buy", quantity=6.434782, price=200.0, currency="EUR",
    ))

    reconcile_holdings(statement)

    assert "GOOGL" not in positions.current_holdings()


def test_crypto_ticker_not_zeroed_by_tr_statement():
    """A TR statement is never authoritative for crypto (lives on Kraken) — absence
    from the statement must not read as 'sold'."""
    positions.add_position(positions.Position(
        ticker="SOL-EUR", name="Solana", type="crypto", bucket="crypto",
    ))
    positions.record_transaction(positions.Transaction(
        date=date(2026, 1, 1), ticker="SOL-EUR", action="buy", quantity=3.0, price=100.0, currency="EUR",
    ))

    statement = make_statement([sell("GOOGL", 1.0, amount=200.0)])
    result = reconcile_holdings(statement)

    assert positions.current_holdings()["SOL-EUR"] == pytest.approx(3.0)
    assert "SOL-EUR" in result["out_of_scope_tickers"]


def test_no_holdings_table_and_no_trades_noops():
    statement = make_statement([])
    result = reconcile_holdings(statement)

    assert result["applied"] is False


# --- _parse_as_of_date --------------------------------------------------------

def test_parse_as_of_date_kontoauszug_header_range_end():
    text = "DAVID KOCH DATUM 01 Jan. 2026 - 18 Juli 2026"
    assert _parse_as_of_date(text, date(2000, 1, 1)) == date(2026, 7, 18)


def test_parse_as_of_date_cash_overview_snapshot_line():
    text = "BARMITTELÜBERSICHT\nZum 18 Juli 2026"
    assert _parse_as_of_date(text, date(2000, 1, 1)) == date(2026, 7, 18)


def test_parse_as_of_date_erstellt_am_footer():
    text = "Erstellt am 2026-07-19 15:33:45 Europe/Berlin"
    assert _parse_as_of_date(text, date(2000, 1, 1)) == date(2026, 7, 19)


def test_parse_as_of_date_explicit_stand_takes_priority():
    text = "Stand: 05.03.2026\nDATUM 01 Jan. 2026 - 18 Juli 2026"
    assert _parse_as_of_date(text, date(2000, 1, 1)) == date(2026, 3, 5)


def test_month_num_handles_umlaut_and_ascii_variants():
    assert _month_num("März") == 3
    assert _month_num("Marz") == 3
    assert _month_num("Juli") == 7
    assert _month_num("Dez.") == 12


# --- _TRADE_ROW_RE -------------------------------------------------------------

@pytest.mark.parametrize("text,action,isin,qty", [
    ("Sell trade US4581401001 INTEL CORP. DL-,001, quantity: 40", "Sell", "US4581401001", "40"),
    ("Sell trade US02079K3059 ALPHABET INC.CL.A DL-,001, quantity: 0.434782",
     "Sell", "US02079K3059", "0.434782"),
    ("Sell trade US38141G1040 GOLDMAN SACHS, quantity: 1.0", "Sell", "US38141G1040", "1.0"),
    ("Buy trade IE00B4L5Y983 ISHARES CORE MSCI WORLD, quantity: 2", "Buy", "IE00B4L5Y983", "2"),
])
def test_trade_row_regex_extracts_fields(text, action, isin, qty):
    m = _TRADE_ROW_RE.search(text)
    assert m is not None
    assert m.group("action") == action
    assert m.group("isin") == isin
    assert m.group("qty") == qty
