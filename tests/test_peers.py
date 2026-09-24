"""Tests for modules/finance/peers.py and the /peers endpoints (Chunk 4).

Synthetic universe + monkeypatched fundamentals lookups: no network, no
yfinance, no price cache, and the overrides YAML is redirected to tmp_path so
the real config/peer_overrides.yaml is never touched.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import stock_detail as sd_api
from modules.finance import peers, stock_detail

# SUBJ is a Technology name with a 100 market cap. Band = 50..150.
INFO = {
    "SUBJ": {"sector": "Technology", "marketCap": 100.0, "longName": "Subject Inc"},
    "A": {"sector": "Technology", "marketCap": 120.0, "longName": "A Corp"},      # +20%  in band
    "E": {"sector": "Technology", "marketCap": 149.0, "longName": "E Corp"},      # +49%  in band
    "B": {"sector": "Technology", "marketCap": 60.0, "longName": "B Corp"},       # -40%  in band
    "F": {"sector": "Technology", "marketCap": 151.0, "longName": "F Corp"},      # +51%  just outside
    "C": {"sector": "Technology", "marketCap": 200.0, "longName": "C Corp"},      # +100% outside
    "G": {"sector": "Technology", "marketCap": 40.0, "longName": "G Corp"},       # -60%  outside
    "D": {"sector": "Healthcare", "marketCap": 100.0, "longName": "D Corp"},      # wrong sector
    "NOCAP": {"sector": "Technology", "longName": "No Cap"},                      # missing market cap
}


@pytest.fixture(autouse=True)
def synthetic_world(monkeypatch, tmp_path):
    monkeypatch.setattr(stock_detail, "get_info", lambda t: INFO.get(t.upper(), {}))
    monkeypatch.setattr(peers, "universe", lambda: [*INFO.keys(), "^GSPC"])
    monkeypatch.setattr(
        stock_detail, "period_returns", lambda t: {"ytd": 0.10, "1y": 0.20}
    )
    monkeypatch.setattr(peers, "PEER_OVERRIDES_FILE", tmp_path / "peer_overrides.yaml")
    monkeypatch.setattr(peers, "_cache", None)
    monkeypatch.setattr(peers, "_cache_mtime", None)


def test_peer_auto_derivation():
    # In-band (same sector, within +/-50%) come first, nearest market cap first.
    assert peers.auto_derive_peers("SUBJ", n=3) == ["A", "E", "B"]
    # Wrong sector / missing market cap never appear; asking for more tops the
    # list up with the nearest same-sector names *outside* the band.
    assert peers.auto_derive_peers("SUBJ", n=4) == ["A", "E", "B", "F"]
    everything = peers.auto_derive_peers("SUBJ", n=20)
    assert "D" not in everything and "NOCAP" not in everything and "SUBJ" not in everything


def test_peer_band_flags_in_table():
    table = peers.peer_table("SUBJ", n=4)
    assert table["source"] == "auto"
    assert [r["ticker"] for r in table["peers"]] == ["SUBJ", "A", "E", "B", "F"]
    assert table["peers"][0]["is_subject"] is True
    assert [r["in_band"] for r in table["peers"][1:]] == [True, True, True, False]


def test_peer_universe_excludes_indices_fx_and_crypto(monkeypatch):
    from modules.finance import buckets, positions, watchlist

    monkeypatch.undo()  # this test wants the real universe() with its inputs faked
    monkeypatch.setattr(watchlist, "universe", lambda: ["ADBE", "^GSPC", "EURUSD=X", "BTC-USD"])
    monkeypatch.setattr(buckets, "_load_ticker_bucket_map", lambda *a, **k: {"MSFT": "single_stocks", "ETH-USD": "crypto"})
    monkeypatch.setattr(positions, "current_holdings", lambda: {"NVDA": 1.0, "adbe": 2.0})
    assert peers.universe() == ["ADBE", "MSFT", "NVDA"]


def test_peer_override_wins():
    saved = peers.set_override("SUBJ", ["g", "c", "G", "SUBJ", "bad ticker!"])
    assert saved == ["G", "C"]  # upper-cased, de-duped, subject and invalid dropped

    assert peers.resolve_peers_with_source("SUBJ") == (["G", "C"], "override")
    table = peers.peer_table("SUBJ")
    assert table["source"] == "override"
    assert [r["ticker"] for r in table["peers"]] == ["SUBJ", "G", "C"]
    # Custom peers were not band-filtered, so no in_band claim is made for them.
    assert all(r["in_band"] is None for r in table["peers"][1:])


def test_peer_clear_override():
    peers.set_override("SUBJ", ["G"])
    assert peers.resolve_peers_with_source("SUBJ")[1] == "override"

    assert peers.set_override("SUBJ", []) == []
    assert peers.resolve_peers_with_source("SUBJ") == (["A", "E", "B", "F"], "auto")


def test_peer_override_persists_across_reload(tmp_path):
    peers.set_override("SUBJ", ["G", "C"])
    # Drop the in-memory cache, as a fresh process would have.
    peers._cache, peers._cache_mtime = None, None
    assert peers.resolve_peers("SUBJ") == ["G", "C"]
    assert "SUBJ" in (tmp_path / "peer_overrides.yaml").read_text(encoding="utf-8")


def test_peer_auto_empty_when_subject_has_no_sector_or_cap():
    assert peers.auto_derive_peers("NOCAP") == []
    assert peers.auto_derive_peers("UNKNOWN") == []


# --- endpoints ----------------------------------------------------------------

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(sd_api.router, prefix="/api/finance")
    return TestClient(app)


def test_peers_endpoints(client):
    body = client.get("/api/finance/peers/SUBJ").json()
    assert body["source"] == "auto"
    assert body["peers"][0]["ticker"] == "SUBJ" and body["peers"][0]["is_subject"]
    assert len(body["peers"]) == 5

    patched = client.patch("/api/finance/peers/SUBJ", json={"peers": ["G", "C"]}).json()
    assert patched["source"] == "override"
    assert [r["ticker"] for r in patched["peers"]] == ["SUBJ", "G", "C"]
    assert client.get("/api/finance/peers/SUBJ").json()["source"] == "override"

    cleared = client.patch("/api/finance/peers/SUBJ", json={"peers": []}).json()
    assert cleared["source"] == "auto"


def test_peers_endpoint_rejects_bad_ticker(client):
    assert client.get("/api/finance/peers/bad%20ticker").status_code == 422
