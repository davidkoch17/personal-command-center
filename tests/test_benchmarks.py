"""Tests for modules/finance/benchmarks.py and GET /benchmarks/compare (Chunk 5).

Synthetic, deterministic price series stand in for the four benchmark tickers;
``benchmarks.get_closes`` is monkeypatched so nothing touches the network or the
real price cache.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import benchmarks as bench_api
from core.config import BENCHMARKS, DEFAULT_RISK_FREE_RATE
from modules.finance import benchmarks as bm
from modules.finance import risk

# ~4 years of business days ending today, so 1Y and 3Y windows are both full.
N = 1050
DATES = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=N)


def _walk(seed: int, drift: float, beta_to_market: float, market: np.ndarray) -> pd.Series:
    """Price path = common market factor * beta + idiosyncratic noise."""
    idio = np.random.default_rng(seed).normal(0, 0.006, N)
    rets = drift + beta_to_market * market + idio
    return pd.Series(100 * np.cumprod(1 + rets), index=DATES)


@pytest.fixture
def closes(monkeypatch):
    market = np.random.default_rng(0).normal(0, 0.008, N)
    series = {
        BENCHMARKS["MSCI_WORLD"]["ticker"]: _walk(1, 0.0004, 1.0, market),
        BENCHMARKS["SPY"]["ticker"]: _walk(2, 0.0005, 1.1, market),
        BENCHMARKS["DAX"]["ticker"]: _walk(3, 0.0003, 0.6, market),
        BENCHMARKS["STOXX_600"]["ticker"]: _walk(4, 0.0002, 0.5, market),
    }
    monkeypatch.setattr(bm, "get_closes", lambda t: series.get(t, pd.Series(dtype="float64")))
    return series


def test_benchmark_metrics_returns_expected_shape(closes):
    m = bm.benchmark_metrics("1y")

    assert list(m) == ["MSCI_WORLD", "SPY", "DAX", "STOXX_600"]  # display order
    for key, row in m.items():
        assert set(row) == {"return", "vol", "sharpe", "correlation_to_msci"}, key
        assert all(v is not None for v in row.values()), key
        assert row["vol"] > 0 and -1 <= row["correlation_to_msci"] <= 1


def test_metrics_reuse_risk_module_and_shared_rfr(closes):
    """vol / Sharpe come from risk.py (same hardcoded RFR as the Optimization tab)."""
    frame = bm._aligned_window("1y")
    rets = frame["SPY"].pct_change().dropna()
    m = bm.benchmark_metrics("1y")["SPY"]

    assert m["vol"] == pytest.approx(risk.annualized_vol(rets))
    assert m["sharpe"] == pytest.approx(risk.sharpe(rets, DEFAULT_RISK_FREE_RATE))
    assert m["return"] == pytest.approx(frame["SPY"].iloc[-1] / frame["SPY"].iloc[0] - 1)
    assert bm.compare("1y")["risk_free_rate"] == DEFAULT_RISK_FREE_RATE


def test_msci_correlation_to_self_is_one(closes):
    assert bm.benchmark_metrics("1y")["MSCI_WORLD"]["correlation_to_msci"] == pytest.approx(1.0)


def test_correlation_matrix_is_symmetric(closes):
    c = bm.benchmark_correlation_matrix("1y")
    m = np.array(c["matrix"])

    assert m.shape == (4, 4)
    assert c["keys"] == ["MSCI_WORLD", "SPY", "DAX", "STOXX_600"]
    assert c["labels"][0] == "MSCI World"
    assert np.allclose(m, m.T)  # corr(A, B) == corr(B, A)


def test_correlation_diagonal_is_one(closes):
    m = np.array(bm.benchmark_correlation_matrix("3y")["matrix"])
    assert np.allclose(np.diag(m), 1.0)


def test_correlation_column_matches_matrix_row(closes):
    """The KPI table's correlation column and the heatmap read the same numbers."""
    metrics = bm.benchmark_metrics("1y")
    matrix = bm.benchmark_correlation_matrix("1y")["matrix"]
    for i, key in enumerate(bm.ORDER):
        assert metrics[key]["correlation_to_msci"] == pytest.approx(matrix[i][0])


def test_indexed_series_start_at_100(closes):
    for period in ("1m", "1y", "all"):
        rows = bm.benchmark_indexed_series(period)
        first = rows[0]
        assert all(first[k] == pytest.approx(100.0) for k in bm.ORDER), period
        assert rows[0]["date"] < rows[-1]["date"]


def test_period_1Y_vs_3Y_return_differs(closes):
    one, three = bm.benchmark_metrics("1y"), bm.benchmark_metrics("3y")
    for key in bm.ORDER:
        assert one[key]["return"] != pytest.approx(three[key]["return"], abs=1e-3), key
    assert len(bm.benchmark_indexed_series("3y")) > len(bm.benchmark_indexed_series("1y"))


def test_period_is_case_insensitive_and_supports_3m_6m(closes):
    assert bm.compare("1Y")["period"] == "1y"
    assert bm.compare("bogus")["period"] == "1y"
    lens = {p: len(bm.benchmark_indexed_series(p)) for p in ("1m", "3m", "6m", "1y")}
    assert lens["1m"] < lens["3m"] < lens["6m"] < lens["1y"]


def test_misaligned_trading_calendars_share_one_window(closes, monkeypatch):
    """DAX closed on days the others traded: every series is cut to the common dates."""
    dax_t = BENCHMARKS["DAX"]["ticker"]
    closes[dax_t] = closes[dax_t].drop(closes[dax_t].index[-60::7])  # ~8 holidays in the last 60 days
    rows = bm.benchmark_indexed_series("1y")
    dax_dates = set(d.date().isoformat() for d in closes[dax_t].index)

    assert all(r["date"] in dax_dates for r in rows)
    assert all(set(r) == {"date", *bm.ORDER} for r in rows)  # no NaN holes


def test_unavailable_benchmark_is_skipped_not_fatal(closes, monkeypatch):
    dax_t = BENCHMARKS["DAX"]["ticker"]
    monkeypatch.setattr(bm, "get_closes", lambda t: pd.Series(dtype="float64") if t == dax_t else closes[t])

    out = bm.compare("1y")
    dax_meta = next(b for b in out["benchmarks"] if b["key"] == "DAX")

    assert dax_meta["available"] is False
    assert out["metrics"]["DAX"] == {"return": None, "vol": None, "sharpe": None, "correlation_to_msci": None}
    assert out["correlation"]["keys"] == ["MSCI_WORLD", "SPY", "STOXX_600"]
    assert len(out["correlation"]["matrix"]) == 3
    assert all("DAX" not in row for row in out["series"])
    assert out["metrics"]["SPY"]["return"] is not None  # the rest still work


def test_no_data_at_all(monkeypatch):
    monkeypatch.setattr(bm, "get_closes", lambda t: pd.Series(dtype="float64"))
    out = bm.compare("1y")
    assert out["series"] == [] and out["correlation"]["matrix"] == []
    assert out["start"] is None and all(not b["available"] for b in out["benchmarks"])
    assert all(v["return"] is None for v in out["metrics"].values())


# --- endpoint -----------------------------------------------------------------

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(bench_api.router, prefix="/api/finance")
    return TestClient(app)


def test_benchmarks_compare_endpoint(client, closes):
    body = client.get("/api/finance/benchmarks/compare?period=1Y").json()

    assert body["period"] == "1y"
    assert [b["key"] for b in body["benchmarks"]] == ["MSCI_WORLD", "SPY", "DAX", "STOXX_600"]
    assert set(body["metrics"]) == set(bm.ORDER)
    assert len(body["correlation"]["matrix"]) == 4
    assert body["series"][0]["MSCI_WORLD"] == pytest.approx(100.0)

    three = client.get("/api/finance/benchmarks/compare?period=3y").json()
    assert three["metrics"]["SPY"]["return"] != body["metrics"]["SPY"]["return"]


def test_benchmarks_compare_endpoint_default_and_bad_period(client, closes):
    assert client.get("/api/finance/benchmarks/compare").json()["period"] == "1y"
    assert client.get("/api/finance/benchmarks/compare?period=5y").status_code == 422
