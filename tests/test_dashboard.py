"""Smoke tests for modules/finance/dashboard.py (Chunk 2 — Portfolio tab)."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from modules.finance import dashboard, performance as perf_mod, positions
from modules.finance.price_history import LivePrice


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    """Redirect the transaction ledger to a throwaway path, same as test_portfolio.py."""
    monkeypatch.setattr(positions, "TRANSACTIONS_FILE", tmp_path / "transactions.jsonl")
    monkeypatch.setattr(positions, "POSITIONS_FILE", tmp_path / "positions.json")


@pytest.fixture(autouse=True)
def no_network_prices(monkeypatch):
    """summary()/indexed_performance() always fetch the benchmark's own return
    series regardless of holdings — stub it so these tests never touch the
    real price cache / network. Individual tests override with synthetic data
    where they need the benchmark side to actually return something."""
    monkeypatch.setattr(dashboard, "get_returns", lambda ticker: pd.Series(dtype="float64"))


def test_summary_empty_ledger_is_graceful():
    result = dashboard.summary()
    assert result["available"] is False
    assert result["portfolio_value_eur"] == 0
    assert result["day_change_eur"] is None
    assert result["top_holdings"] == []
    assert result["holdings_count"] == 0
    # bucket_allocation() computes off the four configured targets regardless
    # of whether anything is held, so a worst-drift bucket is always present.
    assert result["worst_drift_bucket"] is not None
    assert result["worst_drift_bucket"]["bucket"] in {
        "etf_foundation", "single_stocks", "crypto", "wild_cards",
    }


def test_indexed_performance_empty_ledger_is_graceful():
    result = dashboard.indexed_performance()
    assert result["available"] is False
    assert result["series"] == []


def test_holdings_with_day_change_computes_from_price_history(monkeypatch):
    positions.record_transaction(positions.Transaction(
        date=date(2026, 1, 5), ticker="AAPL", action="buy", quantity=10.0, price=100.0, currency="USD",
    ))

    closes = pd.Series([200.0, 220.0], index=pd.date_range("2026-01-01", periods=2, freq="D"))
    monkeypatch.setattr(dashboard, "get_closes", lambda ticker: closes)
    monkeypatch.setattr(
        dashboard, "latest_price_eur",
        lambda ticker: LivePrice(
            ticker=ticker, native_price=220.0, native_currency="USD", fx_rate=0.9, eur_price=198.0,
        ),
    )

    rows = dashboard.holdings_with_day_change()

    assert len(rows) == 1
    row = rows[0]
    assert row["ticker"] == "AAPL"
    assert row["value_eur"] == 1980.0  # 198 EUR/share * 10 shares
    assert row["day_change_pct"] == pytest.approx((220.0 - 200.0) / 200.0)
    assert row["weight"] == 1.0


def test_indexed_performance_two_benchmarks_diverge(monkeypatch):
    """The indexed-performance chart must actually respond to the benchmark
    param — same underlying risk Item A2's regression test guards for beta."""
    positions.record_transaction(positions.Transaction(
        date=date(2026, 1, 5), ticker="AAPL", action="buy", quantity=10.0, price=100.0, currency="USD",
    ))
    dates = pd.date_range("2026-01-01", periods=10, freq="D")
    # portfolio_returns() -> holdings_value_series() calls get_closes via
    # performance.py's own imported name, not dashboard's — patch both.
    port_closes = pd.Series([100.0 + i for i in range(10)], index=dates)
    monkeypatch.setattr(perf_mod, "get_closes", lambda ticker: port_closes)

    def bench_returns(ticker):
        if ticker == "URTH":  # MSCI World
            return pd.Series([0.01] * 9, index=dates[1:])
        return pd.Series([0.05] * 9, index=dates[1:])  # DAX (^GDAXI) and anything else

    monkeypatch.setattr(dashboard, "get_returns", bench_returns)

    msci = dashboard.indexed_performance(period="all", benchmark="MSCI_WORLD")
    dax = dashboard.indexed_performance(period="all", benchmark="DAX")

    assert msci["available"] is True
    assert dax["available"] is True
    assert msci["series"][-1]["benchmark"] != dax["series"][-1]["benchmark"]


def test_summary_reports_the_snapshot_date_the_ytd_euro_figure_comes_from(monkeypatch):
    """Chunk 8: the € YTD is only as fresh as the last daily snapshot — say when that was."""
    import pandas as pd

    from modules.finance import dashboard as dash

    monkeypatch.setattr(dash, "holdings_with_day_change", lambda: [
        {"ticker": "A", "name": "A", "bucket": "single_stocks", "bucket_source": "map", "value_eur": 100.0,
         "day_change_pct": 0.01, "day_change_eur": 1.0, "weight": 1.0}])
    monkeypatch.setattr(dash, "portfolio_returns", lambda *a, **k: pd.Series(dtype="float64"))
    monkeypatch.setattr(dash, "get_returns", lambda t, freq="D": pd.Series(dtype="float64"))
    monkeypatch.setattr(dash, "_worst_drift_bucket", lambda: None)
    monkeypatch.setattr(dash, "position_period_pnl", lambda: {"count": 1, "pnl_ytd_total": 42.0, "as_of": "2026-09-25"})

    out = dash.summary()
    assert out["ytd_return_eur"] == 42.0 and out["ytd_as_of"] == "2026-09-25"

    monkeypatch.setattr(dash, "position_period_pnl", lambda: {"count": 0})
    assert dash.summary()["ytd_as_of"] is None
