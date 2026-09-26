"""Regression tests for performance.holdings_value_series / portfolio_returns.

Found while building Chunk 7: the static-weight portfolio value used to be a plain sum of
whatever tickers had data on each date, so it jumped every time a younger holding's
history began — a fake ~+5,600% "return" that poisoned vol / Sharpe / Sortino / VaR.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modules.finance import performance as perf


def _closes(start: str, n: int, base: float, seed: int) -> pd.Series:
    idx = pd.bdate_range(start, periods=n)
    return pd.Series(base * np.cumprod(1 + np.random.default_rng(seed).normal(0.0004, 0.01, n)), index=idx)


@pytest.fixture
def two_holdings(monkeypatch):
    old = _closes("2020-01-01", 900, 100.0, 1)         # long history
    young = _closes("2021-03-01", 400, 10.0, 2)        # starts ~14 months later, much smaller value
    series = {"OLD": old, "YOUNG": young}
    monkeypatch.setattr(perf, "get_closes", lambda t: series.get(t, pd.Series(dtype="float64")))
    return old, young


def test_value_series_starts_when_the_youngest_holding_starts(two_holdings):
    old, young = two_holdings
    values = perf.holdings_value_series({"OLD": 5.0, "YOUNG": 50.0})

    assert values.index.min() == young.index.min()
    assert values.index.max() == min(old.index.max(), young.index.max()) or values.index.max() == old.index.max()
    # every value is the true two-holding sum (no partial sums from before YOUNG existed)
    day = values.index[10]
    assert values.loc[day] == pytest.approx(5.0 * old.ffill().loc[day] + 50.0 * young.loc[day])


def test_no_fake_jump_when_a_younger_holding_begins(two_holdings):
    rets = perf.portfolio_returns({"OLD": 5.0, "YOUNG": 50.0})

    assert not rets.empty
    assert rets.abs().max() < 0.10  # daily-vol-1% data: nothing near the old +5,000% artefact


def test_missing_history_is_still_skipped(two_holdings):
    only_old = perf.holdings_value_series({"OLD": 5.0, "GHOST": 3.0})  # GHOST has no data
    assert len(only_old) == 900 and only_old.index.min() == two_holdings[0].index.min()
    assert perf.holdings_value_series({"GHOST": 1.0}).empty
