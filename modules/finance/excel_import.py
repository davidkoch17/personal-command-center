"""Excel import: Amex / bank .xlsx -> data/expenses.csv + data/income.csv.

David drops monthly card/bank exports into ``0_Inbox/Finance_Imports/``. This
module (Phase B § c "Excel import"):

1. Picks an import **profile** from ``config/import_profiles.yaml`` per file
   (matched by a filename keyword) — the profile maps the source's column
   headers to the standard ``date / amount / description`` fields and declares
   the amount's sign convention + number format.
2. Splits each row into an **expense** or **income** by sign, and categorizes
   expenses with keyword rules; descriptions no rule matches go to a single
   **Claude fallback** call (``claude -p``, free on David's Max plan) that labels
   the leftovers. If Claude is unavailable the rows keep the ``Uncategorized``
   default — the import never fails on the categorizer.
3. Appends to ``data/expenses.csv`` (``date, amount_eur, category, source,
   raw_description, imported_from_file``) and ``data/income.csv`` (``date,
   amount_eur, source, raw_description``).

**Idempotent:** every written row carries its source filename; re-importing the
same file skips rows already present (keyed on date + amount + description +
file), so a re-run never double-counts.

Run:
    python -m modules.finance.excel_import            # import every file in the inbox
    python -m modules.finance.excel_import --no-claude # keyword-only (skip Claude fallback)
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

from core.config import (
    EXPENSES_CSV,
    FINANCE_IMPORTS_DIR,
    IMPORT_PROFILES_FILE,
    INCOME_CSV,
    get_logger,
)
from modules.finance._csv_store import read_rows, write_rows

logger = get_logger(__name__)

EXPENSE_COLUMNS = ["date", "amount_eur", "category", "source", "raw_description", "imported_from_file"]
INCOME_COLUMNS = ["date", "amount_eur", "source", "raw_description"]


# --- Config -----------------------------------------------------------------

def load_config() -> dict:
    """Parse ``import_profiles.yaml`` (profiles + categorization rules)."""
    with IMPORT_PROFILES_FILE.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def select_profile(filename: str, profiles: dict) -> tuple[str, dict]:
    """Pick the profile whose ``match`` keyword appears in ``filename``.

    Falls back to the ``generic`` profile (English headers) when nothing matches.
    """
    name = filename.lower()
    for key, prof in profiles.items():
        for token in prof.get("match", []) or []:
            if token.lower() in name:
                return key, prof
    return "generic", profiles.get("generic", {})


# --- Parsing ----------------------------------------------------------------

def _parse_amount(raw, decimal: str, thousands: str) -> Optional[float]:
    """Parse a localized money string/number to a float (None if unparseable)."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if not s:
        return None
    s = re.sub(r"[^\d\-,.\s]", "", s).replace(" ", "")
    if thousands:
        s = s.replace(thousands, "")
    if decimal and decimal != ".":
        s = s.replace(decimal, ".")
    try:
        return float(s)
    except ValueError:
        logger.warning("Unparseable amount %r", raw)
        return None


def _parse_date(raw, fmt: Optional[str]) -> Optional[str]:
    """Parse a cell into an ISO ``YYYY-MM-DD`` string (None if unparseable)."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    try:
        ts = pd.to_datetime(raw, format=fmt) if fmt else pd.to_datetime(raw, dayfirst=True)
    except (ValueError, TypeError):
        logger.warning("Unparseable date %r", raw)
        return None
    if pd.isna(ts):
        return None
    return ts.date().isoformat()


def parse_file(path: Path, profile: dict) -> list[dict]:
    """Read one .xlsx into normalized rows ``{date, amount, description, is_income}``.

    ``amount`` is the absolute EUR magnitude; ``is_income`` is derived from the
    profile's sign convention. Rows missing a date or amount are dropped.
    """
    cols = profile.get("columns", {})
    df = pd.read_excel(path, sheet_name=profile.get("sheet", 0), header=profile.get("header_row", 0))
    df.columns = [str(c).strip() for c in df.columns]

    missing = [src for src in cols.values() if src not in df.columns]
    if missing:
        raise ValueError(
            f"{path.name}: profile columns {missing} not found. "
            f"Available: {list(df.columns)}"
        )

    sign = profile.get("amount_sign", "inflow_positive")
    decimal = profile.get("decimal", ".")
    thousands = profile.get("thousands", ",")
    date_fmt = profile.get("date_format")

    rows: list[dict] = []
    for _, r in df.iterrows():
        iso = _parse_date(r.get(cols["date"]), date_fmt)
        amount = _parse_amount(r.get(cols["amount"]), decimal, thousands)
        if iso is None or amount is None:
            continue
        desc = str(r.get(cols["description"]) or "").strip()
        # Sign -> income vs expense. expense_positive: +amount = spend.
        if sign == "expense_positive":
            is_income = amount < 0          # a credit/refund on a card
        else:                                # inflow_positive (bank)
            is_income = amount > 0
        rows.append({
            "date": iso,
            "amount": round(abs(amount), 2),
            "description": desc,
            "is_income": is_income,
        })
    return rows


# --- Categorization ---------------------------------------------------------

def categorize_keyword(description: str, cat_cfg: dict) -> Optional[str]:
    """Return a category if a keyword rule matches the description, else None."""
    d = description.lower()
    for rule in cat_cfg.get("rules", []):
        for kw in rule.get("keywords", []):
            if kw.lower() in d:
                return rule["category"]
    return None


def looks_like_income(description: str, cat_cfg: dict) -> bool:
    """Whether the description matches an income keyword (salary, refund, …)."""
    d = description.lower()
    return any(kw.lower() in d for kw in cat_cfg.get("income_keywords", []))


def _claude_categorize(descriptions: list[str], categories: list[str]) -> dict[str, str]:
    """Label unknown descriptions via one ``claude -p`` call (best-effort).

    Returns ``{description: category}``. On any failure returns ``{}`` so the
    caller falls back to the ``Uncategorized`` default — the import never breaks
    on the categorizer.
    """
    if not descriptions:
        return {}
    try:
        from modules.agents.claude_cli import run_claude
    except Exception as exc:  # noqa: BLE001
        logger.warning("Claude CLI unavailable, skipping fallback: %s", exc)
        return {}

    numbered = "\n".join(f"{i}. {d}" for i, d in enumerate(descriptions))
    prompt = (
        "You categorize German/English bank-transaction descriptions for a "
        "personal-finance tracker. Choose ONE category per item from EXACTLY this "
        f"list: {', '.join(categories)}.\n"
        "Return ONLY a JSON object mapping the item number (as a string) to the "
        "chosen category, no prose.\n\n"
        f"Items:\n{numbered}\n"
    )
    try:
        raw = run_claude(prompt, timeout=120)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {}
        mapping = json.loads(match.group(0))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Claude fallback categorization failed: %s", exc)
        return {}

    valid = set(categories)
    out: dict[str, str] = {}
    for k, cat in mapping.items():
        try:
            desc = descriptions[int(k)]
        except (ValueError, IndexError):
            continue
        if cat in valid:
            out[desc] = cat
    return out


# --- Import driver ----------------------------------------------------------

def _row_key(date_iso: str, amount, description: str, source: str) -> tuple:
    return (date_iso, f"{float(amount):.2f}", description, source)


def import_file(path: Path, config: dict, *, use_claude: bool = True) -> dict:
    """Import one .xlsx into the expense/income CSVs. Returns a summary dict."""
    profiles = config.get("profiles", {})
    cat_cfg = config.get("categorization", {})
    default_cat = cat_cfg.get("default", "Uncategorized")
    profile_name, profile = select_profile(path.name, profiles)
    logger.info("Importing %s with profile '%s'", path.name, profile_name)

    parsed = parse_file(path, profile)

    # Existing rows -> dedupe keys (idempotent re-import). Keyed on the stable
    # source (profile) rather than the filename, which the income schema omits.
    existing_exp = read_rows(EXPENSES_CSV)
    existing_inc = read_rows(INCOME_CSV)
    seen = {
        _row_key(r["date"], r["amount_eur"], r["raw_description"], r.get("source", ""))
        for r in (existing_exp + existing_inc)
    }

    new_expenses: list[dict] = []
    new_income: list[dict] = []
    unknown_descs: list[str] = []

    for row in parsed:
        key = _row_key(row["date"], row["amount"], row["description"], profile_name)
        if key in seen:
            continue
        seen.add(key)
        is_income = row["is_income"] or looks_like_income(row["description"], cat_cfg)
        if is_income:
            new_income.append({
                "date": row["date"],
                "amount_eur": row["amount"],
                "source": profile_name,
                "raw_description": row["description"],
            })
            continue
        category = categorize_keyword(row["description"], cat_cfg)
        exp = {
            "date": row["date"],
            "amount_eur": row["amount"],
            "category": category or default_cat,
            "source": profile_name,
            "raw_description": row["description"],
            "imported_from_file": path.name,
        }
        if category is None:
            unknown_descs.append(row["description"])
        new_expenses.append(exp)

    # Claude fallback for the still-uncategorized expense descriptions.
    if use_claude and unknown_descs:
        categories = [r["category"] for r in cat_cfg.get("rules", [])]
        labelled = _claude_categorize(sorted(set(unknown_descs)), categories)
        if labelled:
            for exp in new_expenses:
                if exp["category"] == default_cat and exp["raw_description"] in labelled:
                    exp["category"] = labelled[exp["raw_description"]]

    if new_expenses:
        write_rows(EXPENSES_CSV, existing_exp + new_expenses, EXPENSE_COLUMNS)
    if new_income:
        write_rows(INCOME_CSV, existing_inc + new_income, INCOME_COLUMNS)

    summary = {
        "file": path.name,
        "profile": profile_name,
        "rows_parsed": len(parsed),
        "expenses_added": len(new_expenses),
        "income_added": len(new_income),
        "claude_used": bool(use_claude and unknown_descs),
    }
    logger.info("Imported %s: %s", path.name, summary)
    return summary


def import_inbox(*, use_claude: bool = True) -> list[dict]:
    """Import every ``.xlsx`` in ``0_Inbox/Finance_Imports/``. Returns summaries."""
    if not FINANCE_IMPORTS_DIR.exists():
        logger.warning("Finance imports dir missing: %s", FINANCE_IMPORTS_DIR)
        return []
    config = load_config()
    summaries: list[dict] = []
    for path in sorted(FINANCE_IMPORTS_DIR.glob("*.xlsx")):
        if path.name.startswith("~$"):  # Excel lock file
            continue
        try:
            summaries.append(import_file(path, config, use_claude=use_claude))
        except Exception as exc:  # noqa: BLE001 - one bad file must not stall the rest
            logger.exception("Failed to import %s: %s", path.name, exc)
            summaries.append({"file": path.name, "error": str(exc)})
    return summaries


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Import bank/card .xlsx into expenses/income CSVs")
    parser.add_argument("--no-claude", action="store_true", help="keyword-only (skip Claude fallback)")
    args = parser.parse_args()
    results = import_inbox(use_claude=not args.no_claude)
    for r in results:
        logger.info("%s", r)
    logger.info("Done: %d file(s) processed", len(results))


if __name__ == "__main__":
    main()
