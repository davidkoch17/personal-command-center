"""Tests for modules/finance/buckets.py's hybrid bucket resolution (Chunk 2.5).

All tests monkeypatch the YAML-backed seed map with a synthetic dict — no
file I/O, so these never touch the real config/ticker_buckets.yaml.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import positions as pos_api
from modules.finance import buckets, positions


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    """Redirect the transaction/position stores to throwaway paths."""
    monkeypatch.setattr(positions, "TRANSACTIONS_FILE", tmp_path / "transactions.jsonl")
    monkeypatch.setattr(positions, "POSITIONS_FILE", tmp_path / "positions.json")


@pytest.fixture(autouse=True)
def mock_ticker_map(monkeypatch):
    """Stub the ticker->bucket seed map — no real YAML read in these tests."""
    fake_map = {"VWCE.DE": "etf_foundation", "BTC-USD": "crypto"}
    monkeypatch.setattr(buckets, "_load_ticker_bucket_map", lambda *a, **kw: fake_map)


@pytest.fixture
def client():
    """Minimal app with just the positions router — avoids importing
    backend.main (SPA static mount + lifespan schedulers)."""
    app = FastAPI()
    app.include_router(pos_api.router, prefix="/api/finance")
    return TestClient(app)


def test_infer_bucket_from_map():
    assert buckets.infer_bucket("VWCE.DE") == "etf_foundation"
    assert buckets.infer_bucket("btc-usd") == "crypto"  # case-insensitive lookup
    assert buckets.infer_bucket("UNKNOWNXYZ") is None


def test_resolve_bucket_override_wins():
    positions.add_position(positions.Position(
        ticker="VWCE.DE", name="Vanguard All-World", type="etf", bucket="wild_cards",
    ))
    assert buckets.resolve_bucket("VWCE.DE") == "wild_cards"
    assert buckets.resolve_bucket_with_source("VWCE.DE") == ("wild_cards", "override")


def test_resolve_bucket_map_fallback():
    # No Position record at all for BTC-USD -> falls straight through to the map.
    assert buckets.resolve_bucket("BTC-USD") == "crypto"
    assert buckets.resolve_bucket_with_source("BTC-USD") == ("crypto", "map")


def test_resolve_bucket_unassigned_fallback():
    assert buckets.resolve_bucket("SOME_RANDOM_TICKER") == "unassigned"
    assert buckets.resolve_bucket_with_source("SOME_RANDOM_TICKER") == ("unassigned", "unassigned")


def test_patch_position_bucket_endpoint(client):
    resp = client.patch("/api/finance/positions/BTC-USD/bucket", json={"bucket": "wild_cards"})
    assert resp.status_code == 200
    assert resp.json() == {"ticker": "BTC-USD", "bucket": "wild_cards", "source": "override"}

    fetched = positions.get_position("BTC-USD")
    assert fetched is not None
    assert fetched.bucket == "wild_cards"


def test_clear_override(client):
    positions.add_position(positions.Position(
        ticker="BTC-USD", name="Bitcoin", type="crypto", bucket="wild_cards",
    ))

    resp = client.patch("/api/finance/positions/BTC-USD/bucket", json={"bucket": None})

    assert resp.status_code == 200
    # Clearing the override falls back to the (mocked) map's "crypto".
    assert resp.json() == {"ticker": "BTC-USD", "bucket": "crypto", "source": "map"}
    fetched = positions.get_position("BTC-USD")
    assert fetched is not None
    assert fetched.bucket is None
