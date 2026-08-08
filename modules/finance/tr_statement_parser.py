"""Trade Republic account-statement PDF parser (re-runnable).

Root cause this fixes: the ledger (``modules.finance.positions``, an
append-only buy/sell log) only knows about a position if every transaction
against it was recorded. GOOGL/Alphabet was bought, then half-sold — but the
second, closing sell was never appended (no parser existed to produce it), so
``current_holdings()`` still showed ~3.43 shares "held" months after the real
account was fully out of the position.

RESOLVED (verified against a real statement, see below): the original design
assumed a statement's *current holdings* table (Depotübersicht / Portfolio
Overview) would be ground truth and always available, with transaction-history
replay only a fallback — on the theory that replaying trades is fragile (one
missed row silently leaves a closed position looking still-held). That
assumption turned out to be wrong for David's actual export: Trade Republic's
"account statement" is a Kontoauszug (cash-account statement) — it has a
``UMSATZÜBERSICHT`` transaction log and a ``BARMITTELÜBERSICHT`` cash/
money-market overview, but **no Depotübersicht/holdings section at all**. So
the holdings-table path never had anything to work with, and both
:func:`reconcile_holdings` and :func:`update_investments_tr_sheet` silently
no-op'd on every real run — which *is* "a single missed row silently leaves a
closed position looking still-held", just arriving via "the only statement
type this account produces" rather than a parsing slip.

The fix adds a second extraction path — :func:`_extract_trade_rows` — that
reads the ``Handel``/"Sell trade"/"Buy trade" rows out of the transaction
log (via word x-position, not line-regex: TR's PDF wraps one logical row
across 2-3 text lines at inconsistent points, so naive line concatenation
reorders the columns; see git history for the page dumps this was derived
from). :func:`reconcile_holdings` now has two paths:
  - **Holdings table present** (Depotübersicht-style statement): unchanged —
    diff the table against the ledger, ground truth as before.
  - **No holdings table, but trade rows found** (Kontoauszug-style, David's
    actual export): net each ticker's buy(+)/sell(-) quantity from this
    statement's trades, add it to the ledger's current holding, and clamp
    negative results to 0 — a statement proves a sell happened even if the
    ledger never recorded the matching buy, and a brokerage account can't
    hold negative shares, so "would go negative" means "fully closed."
Either way, the result feeds the same corrective-transaction + sheet-write
plumbing, so a ticker that's fully sold — Alphabet included — drops out of
both the ledger and the ``Investments_TR`` sheet.

Extraction has three tiers per page for the holdings table, in order:
  1. pdfplumber's grid-based table extraction (``page.extract_tables()``) —
     most reliable when the PDF has real ruled table lines.
  2. Per-line regex parsing of the page's text layer, for statements that
     render the holdings table without ruled lines.
  3. OCR (Tesseract ``deu+eng``, via ``modules.captures.ocr``) for scanned
     pages with no extractable text layer at all, rasterized with
     pdfplumber's built-in pypdfium2-backed renderer (no poppler/ImageMagick
     needed).
Trade-row extraction (:func:`_extract_trade_rows`) runs independently per page
using ``page.extract_words()`` and TR's fixed column layout; it does not use
OCR, since every real statement seen so far has a native text layer.

Usage (re-runnable — safe to run again on the same or a newer statement):
    python -m modules.finance.tr_statement_parser <path-to-statement.pdf>
    python -m modules.finance.tr_statement_parser <path-to-statement.pdf> --dry-run  # parse only, no writes
"""
from __future__ import annotations

import re
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from core.config import FINANCE_TRACKER_FILE, get_logger
from modules.captures.ocr import OCRUnavailable, ocr_image
from modules.finance.portfolio import NAME_TICKER_MAP

logger = get_logger(__name__)

# Section headers that mark the start of the *current holdings* table vs. the
# *transaction history*. Matched case-insensitively; German + English, since TR
# statements/exports use either depending on account language.
_HOLDINGS_HEADERS = [
    "depotübersicht", "depotuebersicht", "portfolio overview", "positionen",
    "aktuelle positionen", "holdings", "depotbestand",
]
_TRANSACTION_HEADERS = [
    "transaktionen", "transaction history", "trade confirmation",
    "kontoauszug", "umsätze", "umsaetze", "abrechnungen",
]
# Column-header keywords used to classify a *table* (extract_tables()) rather
# than a section title line.
_HOLDINGS_COL_KEYWORDS = {"stück", "stueck", "anzahl", "quantity", "shares", "kurs", "price", "wert", "value"}
_HOLDINGS_NAME_KEYWORDS = {"position", "wertpapier", "instrument", "name"}

_HOLDINGS_ROW_RE = re.compile(
    r"(?P<name>[A-Za-zÀ-ÿ0-9&.\-\s]+?)\s+"
    r"(?P<qty>[\d.,]+)\s*(?:Stk\.?|shares?|Stück|Anteile)?\s+"
    r"(?P<price>[\d.,]+)\s*€?\s+"
    r"(?P<value>[\d.,]+)\s*€?\s*$"
)

# --- Transaction-history ("Kontoauszug") row extraction ---------------------
#
# TR's "account statement" export renders one logical row (date / type /
# description / amounts) across 2-3 physical text lines, and *where* it wraps
# varies row to row — so naive line-by-line concatenation interleaves columns
# out of order. These constants are the fixed x-coordinates (in PDF points)
# of TR's column boundaries, measured directly off a real statement via
# ``page.extract_words()``; row reconstruction below buckets words by column
# using these, not by line.
_DATE_COL_MAX_X = 110.0
_TYPE_COL_MAX_X = 150.0
_DESC_COL_MAX_X = 371.0
_ROW_LINE_TOLERANCE = 1.5  # px: words within this of each other's `top` are the same visual line

_MONTH_ABBR = r"Jan|Feb|M(?:ä|a)rz|Apr|Mai|Juni?|Juli?|Aug|Sep|Okt|Nov|Dez"
_MONTH_TOKEN_RE = re.compile(rf"^(?:{_MONTH_ABBR})\.?$", re.I)
_DE_MONTHS = {
    "jan": 1, "feb": 2, "marz": 3, "apr": 4, "mai": 5, "jun": 6, "juni": 6,
    "jul": 7, "juli": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12,
}

# ISIN -> ticker for the instruments seen on David's real statements. Checked
# before the name-substring NAME_TICKER_MAP since ISINs are unambiguous.
_ISIN_TICKER_MAP = {
    "US4581401001": "INTC",
    "US46625H1005": "JPM",
    "US91324P1021": "UNH",
    "US38141G1040": "GS",
    "US02079K3059": "GOOGL",
    "US01609W1027": "BABA",
    "US05606L1008": "BYDDY",
    "DE000A1K0235": "SMHN",
}

_TRADE_ROW_RE = re.compile(
    r"(?P<action>Sell|Buy)\s+trade\s+"
    r"(?P<isin>[A-Z]{2}[A-Z0-9]{9}\d)\s+"
    r"(?P<name>.+?)\s*,?\s*quantity:\s*(?P<qty>[\d.,]+)",
    re.I,
)


@dataclass
class Holding:
    """One row of the statement's current-holdings table."""

    name: str
    quantity: float
    price: float
    value: float
    ticker: str | None = None


@dataclass
class Trade:
    """One "Handel" (trade) row from a statement's transaction history."""

    date: date
    isin: str
    name: str
    ticker: str | None
    action: str  # "buy" | "sell"
    quantity: float
    amount: float | None = None  # gross proceeds/cost for this fill, if parsed


@dataclass
class ParsedStatement:
    source_file: Path
    as_of_date: date
    holdings: list[Holding] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)

    @property
    def has_holdings_table(self) -> bool:
        return bool(self.holdings)

    @property
    def has_data(self) -> bool:
        """Whether anything at all was extracted (holdings table or trade rows).

        Distinct from :attr:`has_holdings_table`: a trade-history statement
        that fully liquidates every position legitimately parses to an empty
        holdings list after reconciliation — that's real data (see
        :func:`reconcile_holdings`), not a failed parse, and should still
        clear stale sheet rows rather than being treated as "nothing found."
        """
        return bool(self.holdings) or bool(self.trades)


def resolve_ticker(name: str) -> str | None:
    """Best-effort map a statement line's instrument name to a ticker.

    Reuses the same name->ticker table as the legacy portfolio view
    (:data:`modules.finance.portfolio.NAME_TICKER_MAP`), so a position
    resolves to the same ticker everywhere in the app.
    """
    n = name.lower()
    for key, tk in NAME_TICKER_MAP.items():
        if key in n:
            return tk
    return None


def _resolve_trade_ticker(isin: str, name: str) -> str | None:
    """Ticker for a transaction-history row: ISIN lookup first, then name."""
    return _ISIN_TICKER_MAP.get(isin) or resolve_ticker(name)


def _de_number(raw: str) -> float:
    """Parse a German- or English-formatted number (1.234,56 or 1,234.56)."""
    raw = raw.strip().replace("€", "").replace("EUR", "").strip()
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    return float(raw)


def _page_text(page, pdf_name: str, page_no: int) -> str:
    """Text-layer extraction, falling back to OCR for scanned pages."""
    text = (page.extract_text() or "").strip()
    if len(text) >= 20:  # a real text layer has far more than this; short/empty = scanned image
        return text
    logger.info("%s page %d: no text layer, falling back to OCR", pdf_name, page_no)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            img_path = Path(tmp) / f"page_{page_no}.png"
            page.to_image(resolution=300).original.save(img_path)
            return ocr_image(img_path)
    except OCRUnavailable as exc:
        logger.warning("%s page %d: OCR unavailable (%s); page left blank", pdf_name, page_no, exc)
        return ""


def _classify_section(line: str) -> str | None:
    low = line.strip().lower()
    if any(h in low for h in _HOLDINGS_HEADERS):
        return "holdings"
    if any(h in low for h in _TRANSACTION_HEADERS):
        return "transactions"
    return None


def _looks_like_holdings_table(header_row: list[str | None]) -> bool:
    header_text = " ".join(str(c or "").lower() for c in header_row)
    has_name_col = any(k in header_text for k in _HOLDINGS_NAME_KEYWORDS)
    has_metric_col = any(k in header_text for k in _HOLDINGS_COL_KEYWORDS)
    return has_name_col and has_metric_col


def _parse_holdings_table(rows: list[list[str | None]]) -> list[Holding]:
    """Turn a pdfplumber-extracted table (header + data rows) into Holdings.

    Column order is inferred from the header row rather than assumed fixed,
    since exports differ (some put price before quantity, etc.).
    """
    header = [str(c or "").strip().lower() for c in rows[0]]
    name_idx = next((i for i, c in enumerate(header) if any(k in c for k in _HOLDINGS_NAME_KEYWORDS)), 0)
    qty_idx = next((i for i, c in enumerate(header)
                     if any(k in c for k in ("stück", "stueck", "anzahl", "quantity", "shares"))), None)
    price_idx = next((i for i, c in enumerate(header) if "kurs" in c or "price" in c), None)
    value_idx = next((i for i, c in enumerate(header) if "wert" in c or "value" in c), None)

    out: list[Holding] = []
    for row in rows[1:]:
        try:
            name = str(row[name_idx] or "").strip()
            if not name:
                continue
            qty = _de_number(str(row[qty_idx])) if qty_idx is not None and row[qty_idx] else 0.0
            price = _de_number(str(row[price_idx])) if price_idx is not None and row[price_idx] else 0.0
            value = _de_number(str(row[value_idx])) if value_idx is not None and row[value_idx] else 0.0
        except (ValueError, IndexError):
            logger.debug("Skipping unparsable holdings table row: %r", row)
            continue
        out.append(Holding(name=name, quantity=qty, price=price, value=value, ticker=resolve_ticker(name)))
    return out


def _month_num(token: str) -> int | None:
    """German month abbreviation ('Jan.', 'März', 'Juli', ...) -> 1-12."""
    key = token.strip(".").lower().replace("ä", "a")
    return _DE_MONTHS.get(key)


def _parse_as_of_date(full_text: str, fallback: date) -> date:
    """Statement date. Tries, in order:

    1. Explicit 'Stand: 18.07.2026' / 'as of 18.07.2026' (numeric, holdings-
       table-style exports).
    2. The Kontoauszug header's date-range end, e.g. 'DATUM 01 Jan. 2026 -
       18 Juli 2026' -> 18 Juli 2026.
    3. The cash-overview snapshot line, e.g. 'Zum 18 Juli 2026'.
    4. The document-generation footer, 'Erstellt am 2026-07-19 ...'.
    5. ``fallback``.
    """
    m = re.search(r"(?:stand|as of|per)\s*:?\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", full_text, re.I)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))

    m = re.search(rf"-\s*(\d{{1,2}})\.?\s+({_MONTH_ABBR})\.?\s+(\d{{4}})", full_text, re.I)
    if m:
        month = _month_num(m.group(2))
        if month:
            return date(int(m.group(3)), month, int(m.group(1)))

    m = re.search(rf"zum\s+(\d{{1,2}})\.?\s+({_MONTH_ABBR})\.?\s+(\d{{4}})", full_text, re.I)
    if m:
        month = _month_num(m.group(2))
        if month:
            return date(int(m.group(3)), month, int(m.group(1)))

    m = re.search(r"erstellt am\s+(\d{4})-(\d{2})-(\d{2})", full_text, re.I)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    return fallback


def _group_into_lines(words: list[dict]) -> list[list[dict]]:
    """Cluster pdfplumber words into visual lines (same ``top``, left-to-right).

    Used instead of the page's own text-line breaks so trade-row extraction
    can bucket words by x-position (column) independent of how the text
    layer happens to wrap a given row.
    """
    lines: list[list[dict]] = []
    tops: list[float] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(w["top"] - tops[-1]) <= _ROW_LINE_TOLERANCE:
            lines[-1].append(w)
        else:
            lines.append([w])
            tops.append(w["top"])
    return [sorted(ln, key=lambda w: w["x0"]) for ln in lines]


def _is_row_start(line_words: list[dict]) -> bool:
    """A new Kontoauszug row starts with 'DD Mon.' in the DATUM column."""
    date_col = [w for w in line_words if w["x0"] < _DATE_COL_MAX_X]
    if len(date_col) < 2:
        return False
    day, month = date_col[0], date_col[1]
    return bool(re.match(r"^\d{1,2}\.?$", day["text"])) and bool(_MONTH_TOKEN_RE.match(month["text"]))


def _first_amount(words: list[dict]) -> float | None:
    """First parseable monetary value in column order (skips '€'/'EUR' tokens)."""
    for w in words:
        if w["text"] in ("€", "EUR"):
            continue
        try:
            return _de_number(w["text"])
        except ValueError:
            continue
    return None


def _extract_trade_rows(page) -> list[Trade]:
    """Extract 'Handel'/Sell-trade/Buy-trade rows from one Kontoauszug page.

    Reconstructs each logical row from words grouped by (block, column)
    rather than by raw text line — see the x-coordinate constants above and
    the module docstring for why line-based parsing doesn't work here.
    """
    words = page.extract_words()
    lines = _group_into_lines(words)
    start_idxs = [i for i, ln in enumerate(lines) if _is_row_start(ln)]

    trades: list[Trade] = []
    for n, start in enumerate(start_idxs):
        end = start_idxs[n + 1] if n + 1 < len(start_idxs) else len(lines)
        block = [w for ln in lines[start:end] for w in ln]

        type_words = [w["text"] for w in block if _DATE_COL_MAX_X <= w["x0"] < _TYPE_COL_MAX_X]
        if not type_words or type_words[0].lower() != "handel":
            continue

        desc_text = " ".join(w["text"] for w in block if _TYPE_COL_MAX_X <= w["x0"] < _DESC_COL_MAX_X)
        m = _TRADE_ROW_RE.search(desc_text)
        if not m:
            logger.debug("Handel row without a parsable trade description: %r", desc_text)
            continue

        date_words = [w["text"] for w in block if w["x0"] < _DATE_COL_MAX_X]
        day_m = next((t for t in date_words if re.match(r"^\d{1,2}\.?$", t)), None)
        month_m = next((t for t in date_words if _MONTH_TOKEN_RE.match(t)), None)
        year_m = next((t for t in date_words if re.match(r"^\d{4}$", t)), None)
        month_num = _month_num(month_m) if month_m else None
        if not (day_m and month_num and year_m):
            logger.debug("Handel row with unparsable date tokens: %r", date_words)
            continue
        trade_date = date(int(year_m), month_num, int(day_m.rstrip(".")))

        amount = _first_amount([w for w in block if w["x0"] >= _DESC_COL_MAX_X])

        isin = m.group("isin").upper()
        name = m.group("name").strip()
        try:
            qty = _de_number(m.group("qty"))
        except ValueError:
            logger.debug("Handel row with unparsable quantity: %r", m.group("qty"))
            continue

        trades.append(Trade(
            date=trade_date, isin=isin, name=name,
            ticker=_resolve_trade_ticker(isin, name),
            action=m.group("action").lower(), quantity=qty, amount=amount,
        ))
    return trades


def parse_tr_statement(pdf_path: str | Path) -> ParsedStatement:
    """Parse a Trade Republic account-statement PDF into holdings + as-of date.

    Tries grid-based table extraction first (most reliable), then per-line
    regex parsing of the text layer, then OCR for scanned pages. Only rows
    under a *holdings*-classified section/table are kept — a transaction
    history, if present, is not replayed (see module docstring for why).
    """
    import pdfplumber

    pdf_path = Path(pdf_path)
    statement = ParsedStatement(source_file=pdf_path, as_of_date=date.today())
    all_text: list[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            # Tier 1: ruled-line tables.
            found_table = False
            for table in page.extract_tables() or []:
                if len(table) >= 2 and _looks_like_holdings_table(table[0]):
                    statement.holdings.extend(_parse_holdings_table(table))
                    found_table = True

            # Independent of the holdings-table tiers: pull any Kontoauszug-
            # style trade rows off this page too (cheap, and the two never
            # collide — a real statement is one type or the other).
            statement.trades.extend(_extract_trade_rows(page))

            # Tier 2/3: text layer, or OCR if the page has none.
            text = _page_text(page, pdf_path.name, i)
            all_text.append(text)
            if found_table:
                continue

            section: str | None = None
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                new_section = _classify_section(line)
                if new_section:
                    section = new_section
                    continue
                if section == "holdings":
                    m = _HOLDINGS_ROW_RE.match(line)
                    if m:
                        try:
                            statement.holdings.append(Holding(
                                name=m.group("name").strip(),
                                quantity=_de_number(m.group("qty")),
                                price=_de_number(m.group("price")),
                                value=_de_number(m.group("value")),
                                ticker=resolve_ticker(m.group("name")),
                            ))
                        except ValueError:
                            logger.debug("%s: unparsed holdings line: %r", pdf_path.name, line)
                # section == "transactions": intentionally not parsed here —
                # trade-history rows vary too much across export types to be
                # worth over-fitting to one statement's layout, and the
                # holdings table is the authoritative source anyway.

    statement.as_of_date = _parse_as_of_date("\n".join(all_text), statement.as_of_date)
    logger.info(
        "%s: parsed %d holdings row(s) and %d trade row(s), as_of=%s (holdings table %s)",
        pdf_path.name, len(statement.holdings), len(statement.trades), statement.as_of_date,
        "found" if statement.has_holdings_table else "NOT found",
    )
    return statement


def _in_scope_tickers(pos_module, candidate_tickers: set[str]) -> tuple[set[str], list[str]]:
    """Split tickers into (brokerage-scoped, out-of-scope) for a TR statement.

    Scoped to tickers whose recorded ``Position.type`` is ``equity``/``etf``
    (skipping ``crypto``/``cash``): a Trade Republic statement is only ever
    ground truth for what's *in that brokerage account*. David's crypto lives
    on Kraken and would never appear on a TR statement, so "not listed on
    this statement" must not be read as "sold" for those tickers — treating
    the whole ledger as in-scope would silently zero out entirely unrelated
    holdings. Tickers with no known Position metadata are treated as
    in-scope (equity is the default assumption for a TR statement).
    """
    from modules.finance.positions import BROKERAGE_TYPES

    in_scope = {
        t for t in candidate_tickers
        if (pos_module.get_position(t).type if pos_module.get_position(t) else "equity") in BROKERAGE_TYPES
    }
    return in_scope, sorted(candidate_tickers - in_scope)


def _apply_adjustment(pos_module, ticker: str, held: float, target: float,
                       price: float, statement: ParsedStatement, reason: str) -> dict | None:
    """Append a corrective transaction moving ``ticker`` from ``held`` to ``target``.

    Returns the adjustment record, or ``None`` if ``held`` already matches
    ``target`` (nothing to do — this is what makes re-running a statement
    idempotent).
    """
    from modules.finance.positions import Transaction

    diff = round(target - held, 8)
    if abs(diff) <= 1e-6:
        return None
    action = "buy" if diff > 0 else "sell"
    qty = abs(diff)
    note = (
        f"Statement reconciliation ({statement.source_file.name}, as of "
        f"{statement.as_of_date}): {reason}. Adjusting with a {action} of {qty:g} "
        f"@ ~{price:.2f} to match — exact trade date/price/fees unknown from this "
        "statement; correct if you have the real trade confirmation."
    )
    pos_module.record_transaction(Transaction(
        date=statement.as_of_date, ticker=ticker, action=action,
        quantity=qty, price=price, currency="EUR", fees=0.0, notes=note,
    ))
    logger.info("Reconciled %s: %s %.6f @ %.2f (before=%.6f, after=%.6f)",
                ticker, action, qty, price, held, target)
    return {"ticker": ticker, "action": action, "quantity": qty, "price": price,
            "before": held, "after": target}


def _synthesize_holdings(pos_module, current: dict[str, float], tickers: set[str],
                          names: dict[str, str]) -> list[Holding]:
    """Build a :class:`Holding` snapshot from the post-reconciliation ledger.

    Lets a trade-history-only statement (no Depotübersicht section) feed
    :func:`update_investments_tr_sheet` the same way a real holdings table
    would — priced at each ticker's last known transaction price, since the
    statement itself provides no live price for anything still held.
    """
    out: list[Holding] = []
    for ticker in sorted(tickers):
        qty = current.get(ticker, 0.0)
        if abs(qty) <= 1e-9:
            continue
        prior = pos_module.transactions_for(ticker)
        price = prior[-1].price if prior else 0.0
        out.append(Holding(
            name=names.get(ticker, ticker), quantity=qty, price=price,
            value=round(qty * price, 2), ticker=ticker,
        ))
    return out


def reconcile_holdings(statement: ParsedStatement) -> dict:
    """Reconcile the ledger against this statement and close any gap.

    Two paths, depending on what the statement actually contains:

    - **Holdings table present** (Depotübersicht-style export): diff the
      table's per-ticker quantities against the ledger — ground truth. For
      every ticker the ledger still shows held but the statement doesn't (or
      holds less of), append a closing/reducing "sell". For every ticker the
      statement holds *more* of, append a "buy" for the difference.
    - **No holdings table, but trade rows found** (Kontoauszug-style — this is
      what David's real TR export actually is): net each ticker's buy(+)/
      sell(-) quantity from this statement's trade rows, add it to the
      ledger's current holding, and clamp below zero to 0 (a statement proves
      a sell happened even if the ledger never recorded the matching buy, and
      a brokerage account can't hold negative shares — "would go negative"
      means "fully closed"). The resulting current holdings are then
      synthesized into a :class:`Holding` snapshot so
      :func:`update_investments_tr_sheet` can write it exactly like a real
      holdings table.

    Either path is idempotent: re-running against the same statement produces
    a zero diff (see :func:`_apply_adjustment`) the second time.

    No-ops if the statement has neither a holdings table nor trade rows.
    """
    from modules.finance import positions as pos

    if statement.has_holdings_table:
        before = pos.current_holdings()
        statement_qty = {h.ticker: h.quantity for h in statement.holdings if h.ticker}
        unresolved = [h.name for h in statement.holdings if not h.ticker]
        if unresolved:
            logger.warning("%s: could not resolve ticker for: %s", statement.source_file.name, unresolved)

        in_scope, skipped_scope = _in_scope_tickers(pos, set(before) | set(statement_qty))
        if skipped_scope:
            logger.info("Out of scope for this statement (not a TR brokerage holding): %s", skipped_scope)

        adjustments: list[dict] = []
        for ticker in sorted(in_scope):
            held = before.get(ticker, 0.0)
            actual = statement_qty.get(ticker, 0.0)
            holding = next((h for h in statement.holdings if h.ticker == ticker), None)
            if holding:
                price = holding.price
            else:
                # Ticker dropped out of the statement entirely (fully sold) —
                # fall back to its last known transaction price rather than 0,
                # same convention the trade-history path uses.
                prior = pos.transactions_for(ticker)
                price = prior[-1].price if prior else 0.0
            adj = _apply_adjustment(
                pos, ticker, held, actual, price, statement,
                reason=f"ledger showed {held:g}, statement holdings table shows {actual:g}",
            )
            if adj:
                adjustments.append(adj)

        after = pos.current_holdings()
        return {
            "applied": True, "before": before, "after": after,
            "adjustments": adjustments, "out_of_scope_tickers": skipped_scope,
        }

    if not statement.trades:
        logger.warning(
            "%s: no current-holdings table and no trade rows found; skipping reconciliation",
            statement.source_file.name,
        )
        return {"applied": False, "reason": "no holdings table or trade rows", "adjustments": []}

    before = pos.current_holdings()
    unresolved = sorted({t.name for t in statement.trades if not t.ticker})
    if unresolved:
        logger.warning("%s: could not resolve ticker for trade(s): %s", statement.source_file.name, unresolved)

    net_change: dict[str, float] = defaultdict(float)
    fills: dict[str, list[Trade]] = defaultdict(list)
    names: dict[str, str] = {}
    for t in statement.trades:
        if not t.ticker:
            continue
        net_change[t.ticker] += t.quantity if t.action == "buy" else -t.quantity
        fills[t.ticker].append(t)
        names[t.ticker] = t.name

    in_scope, skipped_scope = _in_scope_tickers(pos, set(before) | set(net_change))
    if skipped_scope:
        logger.info("Out of scope for this statement (not a TR brokerage holding): %s", skipped_scope)

    adjustments: list[dict] = []
    clamped: list[str] = []
    for ticker in sorted(in_scope):
        held = before.get(ticker, 0.0)
        raw_target = held + net_change.get(ticker, 0.0)
        target = max(0.0, round(raw_target, 8))
        if target != round(raw_target, 8):
            clamped.append(ticker)
            logger.warning(
                "%s: statement's sells for %s exceed the ledger's recorded holding "
                "(ledger=%.6f, statement net change=%+.6f -> would go negative); "
                "clamping to fully closed (0).",
                statement.source_file.name, ticker, held, net_change.get(ticker, 0.0),
            )

        matching_fills = [f for f in fills.get(ticker, []) if (f.action == "buy") == (target > held)]
        priced_fills = [f for f in matching_fills if f.amount]
        if priced_fills:
            price = sum(f.amount for f in priced_fills) / sum(f.quantity for f in priced_fills)
        else:
            prior = pos.transactions_for(ticker)
            price = prior[-1].price if prior else 0.0

        adj = _apply_adjustment(
            pos, ticker, held, target, price, statement,
            reason=(f"ledger showed {held:g}, this statement's trade rows imply a net "
                    f"change of {net_change.get(ticker, 0.0):+g} -> target {target:g}"),
        )
        if adj:
            adjustments.append(adj)

    after = pos.current_holdings()
    statement.holdings = _synthesize_holdings(pos, after, in_scope, names)
    return {
        "applied": True, "before": before, "after": after,
        "adjustments": adjustments, "out_of_scope_tickers": skipped_scope,
        "clamped_to_zero": clamped,
    }


def _last_data_row(ws) -> int:
    last = 5
    for r in range(5, ws.max_row + 1):
        if ws.cell(row=r, column=2).value is not None:
            last = r
    return last


def update_investments_tr_sheet(statement: ParsedStatement) -> dict:
    """Overwrite the Investments_TR sheet's rows for the statement's month.

    Clears any existing rows tagged with that month first, then writes one row
    per holding still in ``statement.holdings`` — so a position that dropped
    out of the statement (sold) doesn't linger from a prior write. Backs up
    the workbook to ``.bak_trstatement_<timestamp>.xlsx`` first, per the vault
    write rule (Python file I/O only, never the Edit/Write tool).

    No-ops only if the statement had nothing extractable at all — no holdings
    table and no trade rows (a partial/garbled parse should not clobber good
    data). A trade-history statement that reconciles to zero holdings (e.g.
    every position fully sold) still writes — clearing that month's stale
    rows is the whole point; see :func:`reconcile_holdings`.
    """
    if not statement.has_data:
        return {"written": False, "reason": "no holdings table or trade rows"}

    import openpyxl

    month = statement.as_of_date.strftime("%Y-%m")
    bak = FINANCE_TRACKER_FILE.with_name(
        f"Finance_Tracker.bak_trstatement_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )
    shutil.copy2(FINANCE_TRACKER_FILE, bak)
    logger.info("Backed up Finance_Tracker.xlsx -> %s", bak.name)

    wb = openpyxl.load_workbook(FINANCE_TRACKER_FILE)
    ws = wb["Investments_TR"]

    existing_rows = [
        r for r in range(5, ws.max_row + 1)
        if str(ws.cell(row=r, column=3).value or "").strip() == month
    ]
    for r in existing_rows:
        for col in range(2, 9):
            ws.cell(row=r, column=col).value = None
    logger.info("Cleared %d existing %s row(s)", len(existing_rows), month)

    write_start = existing_rows[0] if existing_rows else _last_data_row(ws) + 1
    row = write_start
    for h in statement.holdings:
        if abs(h.quantity) <= 1e-9:
            continue
        ws.cell(row=row, column=2).value = datetime.combine(statement.as_of_date, datetime.min.time())
        ws.cell(row=row, column=3).value = month
        ws.cell(row=row, column=4).value = h.name
        ws.cell(row=row, column=5).value = h.quantity
        ws.cell(row=row, column=6).value = h.price
        ws.cell(row=row, column=7).value = h.value
        ws.cell(row=row, column=8).value = f"TR statement {statement.source_file.name} (as of {statement.as_of_date})"
        row += 1

    wb.save(FINANCE_TRACKER_FILE)
    rows_written = row - write_start
    logger.info("Investments_TR: wrote %d row(s) for %s", rows_written, month)
    return {"written": True, "month": month, "rows_written": rows_written, "backup": str(bak)}


def run(pdf_path: str | Path) -> dict:
    """Parse a TR statement and apply both the ledger reconciliation and the
    Investments_TR sheet update in one re-runnable step."""
    statement = parse_tr_statement(pdf_path)
    reconcile_result = reconcile_holdings(statement)
    sheet_result = update_investments_tr_sheet(statement)
    return {"statement": statement, "reconcile": reconcile_result, "sheet": sheet_result}


if __name__ == "__main__":
    import logging
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if len(sys.argv) not in (2, 3):
        print("Usage: python -m modules.finance.tr_statement_parser <path-to-statement.pdf> [--dry-run]")
        raise SystemExit(1)

    if len(sys.argv) == 3 and sys.argv[2] == "--dry-run":
        st_dry = parse_tr_statement(sys.argv[1])
        print(f"[dry run] Holdings table found: {st_dry.has_holdings_table}")
        print(f"[dry run] Trade rows found: {len(st_dry.trades)}")
        for t in st_dry.trades:
            amt = "n/a" if t.amount is None else f"{t.amount:.2f}"
            print(f"  {t.date} {t.action:<4} {t.name:<30} ticker={t.ticker or '?':<8} "
                  f"qty={t.quantity:>12.6f} amount={amt}")
        raise SystemExit(0)

    from modules.finance import positions as pos
    before_holdings = pos.current_holdings()

    result = run(sys.argv[1])
    st = result["statement"]
    print(f"\nHoldings table found: {st.has_holdings_table}")
    print(f"Trade rows found: {len(st.trades)}")
    print(f"As-of date: {st.as_of_date}")
    print(f"\nLedger before: {before_holdings}")
    print(f"Ledger after:  {result['reconcile'].get('after')}")
    print("\nCurrent holdings (post-reconciliation):")
    for h in st.holdings:
        print(f"  {h.name:<25} ticker={h.ticker or '—':<8} qty={h.quantity:>12.6f} "
              f"price={h.price:>10.2f} value={h.value:>10.2f}")
    print(f"\nLedger reconciliation: {result['reconcile']}")
    print(f"\nSheet update: {result['sheet']}")
