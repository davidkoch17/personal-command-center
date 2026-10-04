"""Anlage KAP structured summary (Chunk 9, Portfolio Tax tab).

NOT an Elster integration (that's a separate, future project) — this produces a
structured preview of what would go into the relevant Anlage-KAP lines, built
from the same ledger/FIFO data as the rest of the finance layer, so David can
sanity-check a filing before entering it by hand.

Each line reports a ``confidence``:

- ``confirmed``  — derived straight from logged transactions / realized trades.
- ``estimated``  — derived, but leans on a live-priced (not official/closing)
  mark, e.g. the current year's not-yet-finished Vorabpauschale.
- ``manual_needed`` — no usable data (e.g. no dividend transactions logged, or
  no Basiszins configured for the year); the row is a placeholder for David to
  fill in by hand.

Crypto sold under the §23 EStG private-sales regime is **not** an Anlage-KAP
line at all (it belongs on Anlage SO) and is reported separately so it isn't
silently dropped from the picture.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from core.config import REALIZED_TRADES_CSV, get_logger
from modules.finance import tax, verlustverrechnung, vorabpauschale
from modules.finance._csv_store import read_rows
from modules.finance.buckets import resolve_bucket
from modules.finance.positions import get_position, list_transactions

logger = get_logger(__name__)


def _ticker_currency(ticker: str) -> str:
    """Position.currency (set from the transaction at stub time) — avoids a
    network quote_currency() lookup for every realized row; falls back to USD,
    the default for every instrument this app currently holds."""
    pos = get_position(ticker)
    return (pos.currency if pos else "USD").upper()


def _dividend_income(tax_year: int) -> dict:
    """Zeile 7's dividend component: gross dividend cash, net of each fund
    payout's Teilfreistellung (stock dividends get no such exemption)."""
    divs = [t for t in list_transactions() if t.action == "dividend" and t.date.year == tax_year]
    if not divs:
        return {
            "gross": 0.0, "net_of_teilfreistellung": 0.0, "confidence": "manual_needed",
            "note": f"no dividend transactions logged for {tax_year} — log them via the ledger, "
                    "or enter the total by hand (Trade Republic statement parsing isn't wired up yet)",
        }
    gross = 0.0
    net = 0.0
    for t in divs:
        amount = t.quantity * t.price
        gross += amount
        pos = get_position(t.ticker)
        is_fund = resolve_bucket(t.ticker) == "etf_foundation" or (pos is not None and pos.type == "etf")
        rate = vorabpauschale.etf_metadata(t.ticker)["teilfreistellung"] if is_fund else 0.0
        net += amount * (1 - rate)
    return {
        "gross": round(gross, 2),
        "net_of_teilfreistellung": round(net, 2),
        "confidence": "confirmed",
        "note": f"{len(divs)} dividend transaction(s) logged for {tax_year}; fund payouts reduced "
                "by their Teilfreistellung, stock dividends counted in full",
    }


def _foreign_capital_income(tax_year: int) -> dict:
    """Zeile 14: realized gains/losses + dividends on non-EUR-currency positions.

    Excludes anything classified into the spekulation_23 pot — crypto's §23
    gains aren't Anlage-KAP "Kapitalerträge" at all. This is a disclosure
    sub-total (for the foreign-tax-credit fields), not an additive line, so it
    overlaps on purpose with Zeile 7 / 8-9 rather than double-counting a
    separate pool of money.
    """
    realized = 0.0
    n_trades = 0
    for row in read_rows(REALIZED_TRADES_CSV):
        if row.get("date_sold", "")[:4] != f"{tax_year:04d}":
            continue
        ticker = row.get("ticker", "")
        if verlustverrechnung.classify_pot(ticker) == "spekulation_23":
            continue
        if _ticker_currency(ticker) == "EUR":
            continue
        try:
            realized += float(row.get("realized_gain_eur") or 0.0)
        except (TypeError, ValueError):
            continue
        n_trades += 1

    dividends = sum(
        t.quantity * t.price for t in list_transactions()
        if t.action == "dividend" and t.date.year == tax_year and _ticker_currency(t.ticker) != "EUR"
    )
    total = round(realized + dividends, 2)
    return {
        "amount_eur": total,
        "confidence": "confirmed",
        "note": f"{n_trades} non-EUR realized trade(s) + non-EUR dividends in {tax_year} "
                "(memo sub-total for the foreign-tax-credit fields, not an additive line)",
    }


def kap_summary(
    tax_year: Optional[int] = None,
    prior_carryforwards: Optional[dict[str, float]] = None,
    sparerpauschbetrag: Optional[float] = None,
) -> dict:
    """Structured Anlage-KAP preview for ``tax_year`` (defaults to the current year).

    ``prior_carryforwards`` overrides the persisted loss-pot store (mainly for
    tests/previews — see :func:`modules.finance.verlustverrechnung.current_pots`).
    ``sparerpauschbetrag`` overrides the default €1,000 allowance (€2,000 married).
    """
    tax_year = tax_year or date.today().year
    allowance = tax.SPARERPAUSCHBETRAG if sparerpauschbetrag is None else float(sparerpauschbetrag)

    pots_result = verlustverrechnung.current_pots(tax_year, prior_carryforwards)
    pots = pots_result["pots"]
    aktien, sonstige, spek23 = pots["aktien"], pots["sonstige"], pots["spekulation_23"]

    dividends = _dividend_income(tax_year)
    foreign = _foreign_capital_income(tax_year)
    vorab = vorabpauschale.compute_for_year(tax_year)

    aktien_taxable = max(0.0, aktien["net_balance"])
    sonstige_taxable = max(0.0, sonstige["net_balance"])
    taxable_capital_income = round(dividends["net_of_teilfreistellung"] + aktien_taxable + sonstige_taxable, 2)
    sparerpauschbetrag_used = round(min(allowance, max(0.0, taxable_capital_income)), 2)

    vorab_confidence = "confirmed"
    if not vorab["rows"]:
        vorab_confidence = "confirmed"  # nothing thesaurierend held — a true zero, not a gap
    elif any(r["confidence"] == "manual_needed" for r in vorab["rows"]):
        vorab_confidence = "manual_needed"
    else:
        vorab_confidence = "estimated"  # the current year's end mark is live-priced, not official

    lines = [
        {
            "zeile_number": "7",
            "label": "Kapitalerträge (Dividenden + Zinsen, nach Teilfreistellung)",
            "amount_eur": dividends["net_of_teilfreistellung"],
            "computation_note": dividends["note"],
            "confidence": dividends["confidence"],
        },
        {
            "zeile_number": "8-9",
            "label": "Gewinne aus Investmentfonds (ETF-Verkäufe)",
            "amount_eur": round(sonstige["this_year_gains"] - sonstige["this_year_losses"], 2),
            "computation_note": f"{sonstige['this_year_gains']:.2f} EUR gains minus "
                                 f"{sonstige['this_year_losses']:.2f} EUR losses from ETF sales in "
                                 f"{tax_year} (FIFO-matched, modules.finance.realized)",
            "confidence": "confirmed",
        },
        {
            "zeile_number": "14",
            "label": "Ausländische Kapitalerträge",
            "amount_eur": foreign["amount_eur"],
            "computation_note": foreign["note"],
            "confidence": foreign["confidence"],
        },
        {
            "zeile_number": "16",
            "label": "Sparerpauschbetrag (ausgenutzt)",
            "amount_eur": sparerpauschbetrag_used,
            "computation_note": f"min({allowance:.2f} EUR allowance, "
                                 f"{taxable_capital_income:.2f} EUR taxable capital income)",
            "confidence": "confirmed",
        },
        {
            "zeile_number": "20",
            "label": "Verluste (Aktien + Sonstige)",
            "amount_eur": round(aktien["this_year_losses"] + sonstige["this_year_losses"], 2),
            "computation_note": f"{aktien['this_year_losses']:.2f} EUR Aktien losses + "
                                 f"{sonstige['this_year_losses']:.2f} EUR Sonstige losses in {tax_year} "
                                 "(feeds the Verlustverrechnungstopf below)",
            "confidence": "confirmed",
        },
        {
            "zeile_number": "41-45",
            "label": "Vorabpauschale (thesaurierende ETFs)",
            "amount_eur": vorab["total_taxable_eur"],
            "computation_note": (
                f"Basiszins {tax_year}: {vorab['basiszins']:.4f}; summed across "
                f"{len(vorab['rows'])} thesaurierend ETF(s), Teilfreistellung applied"
                if vorab["basiszins"] is not None else
                f"no Basiszins configured for {tax_year} — add it to config/basiszins.yaml"
            ),
            "confidence": vorab_confidence,
        },
        {
            "zeile_number": "48",
            "label": "Verlustvortrag Aktien (zum Jahresende)",
            "amount_eur": aktien["new_carryforward"],
            "computation_note": f"prior-year carryforward ({aktien['prior_carryforward']:.2f} EUR) + "
                                 f"{tax_year}'s net result ({aktien['net_balance']:.2f} EUR)",
            "confidence": "confirmed",
        },
        {
            "zeile_number": "49",
            "label": "Verlustvortrag Sonstige (zum Jahresende)",
            "amount_eur": sonstige["new_carryforward"],
            "computation_note": f"prior-year carryforward ({sonstige['prior_carryforward']:.2f} EUR) + "
                                 f"{tax_year}'s net result ({sonstige['net_balance']:.2f} EUR)",
            "confidence": "confirmed",
        },
    ]

    non_kap_note = {
        "label": "Spekulationsgeschäfte Krypto nach §23 EStG",
        "amount_eur": spek23["net_balance"],
        "computation_note": (
            f"{spek23['this_year_gains']:.2f} EUR gains minus {spek23['this_year_losses']:.2f} EUR "
            f"losses from crypto sales held < 365 days in {tax_year}; "
            f"{pots_result['tax_free_crypto_excluded_eur']:.2f} EUR excluded as tax-free "
            "(Spekulationsfrist met, >= 365 days). Goes on Anlage SO, not Anlage KAP."
        ),
        "confidence": "confirmed",
    }

    return {
        "tax_year": tax_year,
        "sparerpauschbetrag": allowance,
        "lines": lines,
        "non_kap_note": non_kap_note,
        "disclaimer": "This is a structured summary of your tax-relevant positions, not an "
                      "official Elster filing. Verify before submitting.",
    }
