"""Peer comparison for the Single Stock tab (Chunk 4) — hybrid auto / custom.

Mirrors Chunk 2.5's bucket resolution: a per-ticker *override* in
``config/peer_overrides.yaml`` wins; otherwise peers are *auto-derived* fresh on
every read. Nothing writes an auto result back into the overrides file (that
would make it indistinguishable from a deliberate choice and break "clear
override").

Auto-derivation is deterministic and offline-friendly: the candidate universe is
a fixed set (watchlist ``Watchlist.md`` + ``config/ticker_buckets.yaml`` +
current holdings), never an open-ended yfinance search, and each candidate's
sector / market cap come from the same 24h-cached snapshot the fundamentals
panel uses. A candidate is a peer when it shares the subject's **sector** and
its market cap is within ±50% of the subject's (:data:`PEER_MARKET_CAP_BAND`).
Peers are ranked by closeness in (log) market cap, ties broken by ticker.

When fewer than ``n`` candidates fall inside the band (a small universe makes
that common) the list is topped up with the nearest same-sector names *outside*
the band, flagged ``in_band=False`` so the UI can say so instead of pretending
they matched.
"""
from __future__ import annotations

import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import yaml

from core.config import DEFAULT_PEER_COUNT, PEER_MARKET_CAP_BAND, PEER_OVERRIDES_FILE, get_logger
from modules.finance import stock_detail

logger = get_logger(__name__)

MAX_CUSTOM_PEERS = 8
_TICKER_OK = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")

# mtime-cached overrides map (same shape/idea as buckets._load_ticker_bucket_map).
_cache: Optional[dict[str, list[str]]] = None
_cache_mtime: Optional[float] = None


# --- overrides file ---------------------------------------------------------

def _load_overrides(path: Optional[Path] = None) -> dict[str, list[str]]:
    global _cache, _cache_mtime
    path = path or PEER_OVERRIDES_FILE  # resolved per call so tests can redirect the file
    if not path.exists():
        return {}
    mtime = path.stat().st_mtime
    if _cache is not None and _cache_mtime == mtime:
        return _cache
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as exc:  # noqa: BLE001
        logger.warning("peer_overrides.yaml unreadable: %s", exc)
        return _cache or {}
    _cache = {
        str(k).upper(): [str(p).upper() for p in v]
        for k, v in raw.items()
        if isinstance(v, list) and v
    }
    _cache_mtime = mtime
    return _cache


def clean_peer_list(subject: str, peers: list[str]) -> list[str]:
    """Normalize a user-supplied list: upper-case, valid tickers only, no dupes,
    never the subject itself, capped at :data:`MAX_CUSTOM_PEERS`."""
    out: list[str] = []
    for p in peers:
        t = str(p).strip().upper()
        if t and t != subject.upper() and _TICKER_OK.match(t) and t not in out:
            out.append(t)
    return out[:MAX_CUSTOM_PEERS]


def set_override(ticker: str, peers: list[str], path: Optional[Path] = None) -> list[str]:
    """Save ``peers`` as ``ticker``'s custom list; an empty list clears the override.

    Returns the cleaned list actually stored. Atomic write (tmp + replace) so a
    crash mid-save can't leave a half-written YAML.
    """
    global _cache, _cache_mtime
    path = path or PEER_OVERRIDES_FILE
    tu = ticker.upper()
    cleaned = clean_peer_list(tu, peers)
    current = dict(_load_overrides(path))
    if cleaned:
        current[tu] = cleaned
    else:
        current.pop(tu, None)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        "# Manual peer lists for the Single Stock tab: TICKER: [peer, peer, ...]\n"
        "# Written by PATCH /api/finance/peers/{ticker}. A ticker with no entry\n"
        "# auto-derives its peers (modules/finance/peers.py). Safe to edit by hand.\n"
        + (yaml.safe_dump(current, sort_keys=True, default_flow_style=False) if current else "{}\n"),
        encoding="utf-8",
    )
    os.replace(tmp, path)
    _cache, _cache_mtime = None, None
    return cleaned


# --- auto derivation --------------------------------------------------------

def _is_equity_like(ticker: str) -> bool:
    """Exclude indices, FX pairs and crypto pairs from the peer universe."""
    t = ticker.upper()
    return not (t.startswith("^") or t.endswith("=X") or re.search(r"-(USD|EUR|GBP|USDT)$", t))


def universe() -> list[str]:
    """Deterministic candidate pool: watchlist ∪ bucket seed map ∪ holdings."""
    from modules.finance import buckets, positions, watchlist

    seen: dict[str, None] = {}
    for t in [*watchlist.universe(), *buckets._load_ticker_bucket_map().keys(), *positions.current_holdings().keys()]:
        tu = str(t).upper()
        if tu and _is_equity_like(tu):
            seen.setdefault(tu, None)
    return list(seen)


def _infos(tickers: list[str]) -> dict[str, dict]:
    """``get_info`` for many tickers concurrently (cached lookups are instant)."""
    if not tickers:
        return {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        return dict(zip(tickers, ex.map(stock_detail.get_info, tickers)))


def _rank_candidates(ticker: str) -> list[dict]:
    """Same-sector candidates, best first: in-band names, then nearest outside it."""
    tu = ticker.upper()
    subject = stock_detail.get_info(tu)
    sector, cap = subject.get("sector"), stock_detail._num(subject.get("marketCap"))
    if not sector or not cap:
        return []
    pool = [t for t in universe() if t != tu]
    ranked: list[dict] = []
    for t, info in _infos(pool).items():
        pcap = stock_detail._num(info.get("marketCap"))
        if info.get("sector") != sector or not pcap:
            continue
        in_band = abs(pcap / cap - 1) <= PEER_MARKET_CAP_BAND
        ranked.append({"ticker": t, "in_band": in_band, "_dist": abs(math.log(pcap / cap))})
    ranked.sort(key=lambda r: (not r["in_band"], r["_dist"], r["ticker"]))
    return [{"ticker": r["ticker"], "in_band": r["in_band"]} for r in ranked]


def auto_derive_peers(ticker: str, n: int = DEFAULT_PEER_COUNT) -> list[str]:
    """Up to ``n`` auto peers for ``ticker`` (same sector, market cap within ±50%,
    topped up with the nearest same-sector names outside the band)."""
    return [r["ticker"] for r in _rank_candidates(ticker)[:n]]


def resolve_peers_with_source(ticker: str, n: int = DEFAULT_PEER_COUNT) -> tuple[list[str], str]:
    """``(peers, source)`` — ``"override"`` if a custom list is saved, else ``"auto"``."""
    override = _load_overrides().get(ticker.upper())
    if override:
        return override, "override"
    return auto_derive_peers(ticker, n), "auto"


def resolve_peers(ticker: str, n: int = DEFAULT_PEER_COUNT) -> list[str]:
    """Just the resolved peer tickers (see :func:`resolve_peers_with_source`)."""
    return resolve_peers_with_source(ticker, n)[0]


# --- table for the UI -------------------------------------------------------

def _row(ticker: str, subject: str, in_band: Optional[bool]) -> dict:
    info = stock_detail.get_info(ticker)
    rets = stock_detail.period_returns(ticker)
    return {
        "ticker": ticker,
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "market_cap": stock_detail._num(info.get("marketCap")),
        "pe_forward": stock_detail._num(info.get("forwardPE")),
        "ytd_return": rets["ytd"],
        "return_1y": rets["1y"],
        "is_subject": ticker == subject,
        "in_band": in_band,
    }


def peer_table(ticker: str, n: int = DEFAULT_PEER_COUNT) -> dict:
    """Subject row first (highlighted), then the resolved peers, each with fundamentals."""
    tu = ticker.upper()
    override = _load_overrides().get(tu)
    if override:
        source, chosen = "override", [{"ticker": p, "in_band": None} for p in override]
    else:
        source, chosen = "auto", _rank_candidates(tu)[:n]
    tickers = [tu] + [c["ticker"] for c in chosen]
    bands = {c["ticker"]: c["in_band"] for c in chosen}
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(lambda t: _row(t, tu, bands.get(t)), tickers))
    return {"ticker": tu, "source": source, "peers": rows}
