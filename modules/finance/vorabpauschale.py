"""Vorabpauschale — advance lump-sum tax on accumulating (thesaurierende) ETFs
that don't distribute (Chunk 9, Portfolio Tax tab; InvStG §18/§20).

Formula (InvStG §18)::

    Vorabpauschale = Fondswert_Jahresanfang * Basiszins * 0.7
    capped at max(0, Fondswert_Jahresende - Fondswert_Jahresanfang - Ausschuettungen)

A Teilfreistellung (partial exemption, InvStG §20) then applies by fund type:
30% for an equity fund (>=51% equity), 15% for a mixed fund (>=25%), 60%/80%
for a property fund. David tags each ETF's type + exemption in
``config/etf_metadata.yaml`` (mtime-cached, same pattern as
``config/ticker_buckets.yaml``); the base rate per year — published by the BMF
each January — lives in ``config/basiszins.yaml``. Only applies to
thesaurierend ETFs in the ``etf_foundation`` bucket.

Year-start/year-end EUR values come from ``data/positions_daily.csv`` (the
existing daily backfill, :mod:`modules.finance.backfill`), so this needs no new
price fetch and no network access.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from core.config import BASISZINS_FILE, ETF_METADATA_FILE, POSITIONS_DAILY_CSV, get_logger
from modules.finance._csv_store import read_rows
from modules.finance.buckets import resolve_bucket

logger = get_logger(__name__)

DEFAULT_TEILFREISTELLUNG = 0.30  # equity fund — the default when an ETF isn't listed at all
VORABPAUSCHALE_FACTOR = 0.7

_etf_map_cache: Optional[dict[str, dict]] = None
_etf_map_mtime: Optional[float] = None
_basiszins_cache: Optional[dict[int, float]] = None
_basiszins_mtime: Optional[float] = None


def _load_etf_metadata(path: Path = ETF_METADATA_FILE) -> dict[str, dict]:
    """``{TICKER: {"type": ..., "teilfreistellung": ...}}`` from the config yaml.

    mtime-cached; returns ``{}`` (never raises) if the file is missing or
    unreadable, so an absent config just means every ETF falls back to the
    thesaurierend/30% default.
    """
    global _etf_map_cache, _etf_map_mtime
    if not path.exists():
        return {}
    mtime = path.stat().st_mtime
    if _etf_map_cache is not None and _etf_map_mtime == mtime:
        return _etf_map_cache
    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except (yaml.YAMLError, OSError) as exc:  # noqa: BLE001
        logger.warning("etf_metadata.yaml unreadable: %s", exc)
        return _etf_map_cache or {}
    _etf_map_cache = {str(k).upper(): v for k, v in raw.items() if isinstance(v, dict)}
    _etf_map_mtime = mtime
    return _etf_map_cache


def etf_metadata(ticker: str) -> dict:
    """``{"type", "teilfreistellung"}`` for ``ticker`` — defaults to a
    thesaurierend equity fund (30% exemption) when the ticker isn't listed."""
    meta = _load_etf_metadata().get(ticker.upper(), {})
    return {
        "type": meta.get("type", "thesaurierend"),
        "teilfreistellung": float(meta.get("teilfreistellung", DEFAULT_TEILFREISTELLUNG)),
    }


def _load_basiszins(path: Path = BASISZINS_FILE) -> dict[int, float]:
    """``{year: rate}`` from the config yaml. mtime-cached; ``{}`` if unreadable."""
    global _basiszins_cache, _basiszins_mtime
    if not path.exists():
        return {}
    mtime = path.stat().st_mtime
    if _basiszins_cache is not None and _basiszins_mtime == mtime:
        return _basiszins_cache
    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except (yaml.YAMLError, OSError) as exc:  # noqa: BLE001
        logger.warning("basiszins.yaml unreadable: %s", exc)
        return _basiszins_cache or {}
    _basiszins_cache = {int(k): float(v) for k, v in raw.items() if v is not None}
    _basiszins_mtime = mtime
    return _basiszins_cache


def basiszins_for_year(year: int) -> Optional[float]:
    """The BMF's published Basiszins for ``year``, or ``None`` if not yet entered."""
    return _load_basiszins().get(year)


def _thesaurierend_etf_tickers() -> list[str]:
    """``etf_foundation``-bucket tickers tagged (or defaulted) thesaurierend."""
    from modules.finance.positions import current_holdings

    return [
        ticker for ticker in current_holdings()
        if resolve_bucket(ticker) == "etf_foundation" and etf_metadata(ticker)["type"] == "thesaurierend"
    ]


def _daily_rows_by_ticker() -> dict[str, list[dict]]:
    by_ticker: dict[str, list[dict]] = {}
    for row in read_rows(POSITIONS_DAILY_CSV):
        by_ticker.setdefault(row["ticker"], []).append(row)
    for rows in by_ticker.values():
        rows.sort(key=lambda r: r["date"])
    return by_ticker


def _value_eur_on_or_after(rows: list[dict], on_or_after: str) -> Optional[float]:
    """First EUR value at/after ``on_or_after`` (ISO date) — the fund's
    start-of-year mark, or its first-ever mark if the position opened mid-year."""
    for r in rows:
        if r["date"] >= on_or_after:
            return float(r["value_eur"])
    return None


def _value_eur_on_or_before(rows: list[dict], on_or_before: str) -> Optional[float]:
    """Latest EUR value at/before ``on_or_before`` — the fund's end-of-year mark,
    or today's live-priced mark for the current (not-yet-finished) tax year."""
    match = None
    for r in rows:
        if r["date"] <= on_or_before:
            match = r
        else:
            break
    return float(match["value_eur"]) if match else None


def _distributions_eur(ticker: str, tax_year: int) -> float:
    """Dividend cash paid on ``ticker`` during ``tax_year`` — same gross
    (qty * price) convention as performance.portfolio_returns' IRR cash flows.
    Nets against the Vorabpauschale cap (a fund that distributed already paid
    out some of its gain, so the advance tax shouldn't double-count it)."""
    from modules.finance.positions import list_transactions

    total = sum(
        t.quantity * t.price for t in list_transactions()
        if t.ticker == ticker and t.action == "dividend" and t.date.year == tax_year
    )
    return round(total, 2)


def compute_for_year(tax_year: Optional[int] = None) -> dict:
    """Per-ETF Vorabpauschale for ``tax_year`` (defaults to the current year).

    A row reports ``confidence: "manual_needed"`` (and ``vorabpauschale: None``)
    when either the year's Basiszins hasn't been entered in
    ``config/basiszins.yaml`` yet, or there's no daily price history for that
    ETF spanning the year — otherwise ``"estimated"`` (the end-of-year mark is
    live-priced, not the fund's official published Fondswert).
    """
    tax_year = tax_year or date.today().year
    basiszins = basiszins_for_year(tax_year)
    start_iso = date(tax_year, 1, 1).isoformat()
    end_iso = date(tax_year, 12, 31).isoformat()
    by_ticker = _daily_rows_by_ticker()

    rows = []
    for ticker in _thesaurierend_etf_tickers():
        series = by_ticker.get(ticker, [])
        start_value = _value_eur_on_or_after(series, start_iso)
        end_value = _value_eur_on_or_before(series, end_iso)
        meta = etf_metadata(ticker)

        if basiszins is None or start_value is None or end_value is None:
            reason = (
                f"no Basiszins configured for {tax_year} — add it to config/basiszins.yaml"
                if basiszins is None else
                "no daily price history for this ETF over this year yet — run the backfill"
            )
            rows.append({
                "ticker": ticker, "fondswert_anfang": start_value, "fondswert_ende": end_value,
                "ausschuettungen": None, "basiszins": basiszins, "vorabpauschale": None,
                "teilfreistellung": meta["teilfreistellung"], "taxable_amount": None,
                "confidence": "manual_needed", "note": reason,
            })
            continue

        distributions = _distributions_eur(ticker, tax_year)
        base = max(0.0, start_value * basiszins * VORABPAUSCHALE_FACTOR)
        actual_gain_cap = max(0.0, end_value - start_value - distributions)
        vorabpauschale = round(min(base, actual_gain_cap), 2)
        taxable = round(vorabpauschale * (1 - meta["teilfreistellung"]), 2)
        rows.append({
            "ticker": ticker,
            "fondswert_anfang": round(start_value, 2),
            "fondswert_ende": round(end_value, 2),
            "ausschuettungen": distributions,
            "basiszins": basiszins,
            "vorabpauschale": vorabpauschale,
            "teilfreistellung": meta["teilfreistellung"],
            "taxable_amount": taxable,
            "confidence": "estimated",
            "note": f"capped at the fund's actual {tax_year} gain (€{actual_gain_cap:,.2f}); "
                    f"{meta['teilfreistellung']:.0%} Teilfreistellung applied",
        })

    total_taxable = round(sum(r["taxable_amount"] for r in rows if r["taxable_amount"] is not None), 2)
    return {
        "tax_year": tax_year,
        "basiszins": basiszins,
        "rows": rows,
        "total_taxable_eur": total_taxable,
    }
