"""Verlustverrechnungstoepfe — German loss-offset pots (Chunk 9, Portfolio Tax tab).

German capital-gains tax law only lets a realized loss offset a gain in the same
category — you can't net an ETF loss against a stock gain, or either against a
crypto loss:

- **Aktien** pot: individual-share (Einzelaktien) sales only. A loss here can
  only offset gains from *other stock sales*.
- **Sonstige** pot: everything else under the Abgeltungsteuer regime — ETFs/
  funds are "Investmentfonds", not "Aktien", for this purpose, so they land
  here even though they're also equities.
- **Spekulation §23**: crypto sold inside the 365-day Spekulationsfrist. This
  isn't actually an Anlage-KAP category at all (private sales under §23 EStG go
  on Anlage SO), so it's reported alongside the other two but clearly flagged as
  a different form/regime. Crypto held >= 365 days is outside the tax net
  entirely — not a gain, not a loss, not netted against anything — so those
  trades are excluded from every pot rather than counted as a zero.

Reads :mod:`modules.finance.realized`'s FIFO trade log; classification per
ticker is bucket-first (Chunk 2.5's resolve_bucket), falling back to the
position's instrument type for wild_cards/unassigned tickers.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Optional

from core.config import REALIZED_TRADES_CSV, TAX_CARRYFORWARDS_FILE, get_logger
from modules.finance._csv_store import read_rows
from modules.finance.buckets import resolve_bucket
from modules.finance.positions import get_position

logger = get_logger(__name__)

POTS = ("aktien", "sonstige", "spekulation_23")
POT_LABELS = {
    "aktien": "Aktien",
    "sonstige": "Sonstige (ETFs / Fonds / Sonstiges)",
    "spekulation_23": "Spekulation nach §23 EStG (Crypto < 365 Tage)",
}
_CRYPTO_SUFFIXES = ("-USD", "-EUR", "-GBP")  # mirrors decision_support's type guess (Chunk 8)
SPEKULATIONSFRIST_DAYS = 365


def _is_crypto_ticker(ticker: str) -> bool:
    return ticker.upper().endswith(_CRYPTO_SUFFIXES)


def classify_pot(ticker: str) -> str:
    """Which loss-offset pot a ticker's realized trades fall into.

    Bucket wins first (single_stocks -> aktien, etf_foundation -> sonstige,
    crypto -> spekulation_23); wild_cards/unassigned tickers fall through to the
    position's instrument type (or the crypto-suffix guess when there's no
    Position record), defaulting to "aktien" when nothing else says otherwise —
    same "uncertain calls default to the equity case" convention as
    ticker_buckets.yaml.
    """
    bucket = resolve_bucket(ticker)
    if bucket == "crypto":
        return "spekulation_23"
    if bucket == "etf_foundation":
        return "sonstige"
    if bucket == "single_stocks":
        return "aktien"

    pos = get_position(ticker)
    instrument_type = pos.type if pos else ("crypto" if _is_crypto_ticker(ticker) else None)
    if instrument_type == "crypto":
        return "spekulation_23"
    if instrument_type == "etf":
        return "sonstige"
    return "aktien"


# --- prior-year carryforward (manual — we don't have past years' ledger data) ----------------

def _load_carryforwards() -> dict[str, float]:
    if not TAX_CARRYFORWARDS_FILE.exists():
        return {}
    try:
        raw = json.loads(TAX_CARRYFORWARDS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:  # noqa: BLE001
        logger.warning("tax_carryforwards.json unreadable: %s", exc)
        return {}
    return {k: float(v) for k, v in raw.items() if k in POTS and isinstance(v, (int, float))}


def get_carryforwards() -> dict[str, float]:
    """Persisted prior-year loss carryforward per pot (0.0 for any pot not set)."""
    saved = _load_carryforwards()
    return {pot: saved.get(pot, 0.0) for pot in POTS}


def set_carryforwards(values: dict[str, float]) -> dict[str, float]:
    """Merge ``values`` (only recognized pot keys) into the persisted store."""
    clean = {pot: float(values[pot]) for pot in POTS if pot in values}
    merged = {**get_carryforwards(), **clean}
    TAX_CARRYFORWARDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TAX_CARRYFORWARDS_FILE.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    logger.info("Loss-pot carryforwards updated: %s", clean)
    return merged


# --- this year's pots -------------------------------------------------------------------------

def current_pots(tax_year: Optional[int] = None, prior_carryforwards: Optional[dict[str, float]] = None) -> dict:
    """This tax year's realized gains/losses per pot, netted against the carryforward.

    ``prior_carryforwards`` overrides the persisted store when given (mainly for
    tests/previews) — pass ``{}`` explicitly to force every pot's carryforward to
    zero rather than reading the saved one.
    """
    tax_year = tax_year or date.today().year
    carry = get_carryforwards() if prior_carryforwards is None else {
        pot: float(prior_carryforwards.get(pot, 0.0)) for pot in POTS
    }

    raw = {pot: {"gains": 0.0, "losses": 0.0} for pot in POTS}
    tax_free_crypto_excluded = 0.0

    for row in read_rows(REALIZED_TRADES_CSV):
        sold = row.get("date_sold", "")
        if sold[:4] != f"{tax_year:04d}":
            continue
        try:
            gain = float(row.get("realized_gain_eur") or 0.0)
            holding_days = int(float(row.get("holding_days") or 0))
        except (TypeError, ValueError):
            continue

        pot = classify_pot(row.get("ticker", ""))
        if pot == "spekulation_23" and holding_days >= SPEKULATIONSFRIST_DAYS:
            # Spekulationsfrist met: tax-free and outside every pot (not even a zero).
            tax_free_crypto_excluded += gain
            continue
        if gain >= 0:
            raw[pot]["gains"] += gain
        else:
            raw[pot]["losses"] += -gain  # store as a positive magnitude

    pots = {}
    for pot in POTS:
        gains = round(raw[pot]["gains"], 2)
        losses = round(raw[pot]["losses"], 2)
        prior = round(carry[pot], 2)
        net_balance = round(gains - losses - prior, 2)
        pots[pot] = {
            "label": POT_LABELS[pot],
            "this_year_gains": gains,
            "this_year_losses": losses,
            "prior_carryforward": prior,
            # Positive = net taxable this year; negative magnitude = loss still
            # carried forward (frontend colors this red/green on that sign).
            "net_balance": net_balance,
            "new_carryforward": round(max(0.0, -net_balance), 2),
        }

    return {
        "tax_year": tax_year,
        "pots": pots,
        "tax_free_crypto_excluded_eur": round(tax_free_crypto_excluded, 2),
        "note": ("the spekulation_23 pot is not an Anlage-KAP line — German tax law reports "
                 "private crypto sales on Anlage SO, not Anlage KAP; see kap_form.py's note."),
    }
