"""Single point of entry for reading Finance_Tracker.xlsx."""
from pathlib import Path
import pandas as pd
from core.config import FINANCE_TRACKER_FILE


def _read(sheet_name: str, header_row: int = 4) -> pd.DataFrame:
    """Read a sheet from the finance tracker; header_row is 0-indexed."""
    df = pd.read_excel(FINANCE_TRACKER_FILE, sheet_name=sheet_name, header=header_row)
    # Drop leading "Unnamed" columns (the workbook has a blank col A everywhere)
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    # Drop fully empty rows
    df = df.dropna(how="all")
    return df


def transactions() -> pd.DataFrame:
    """Columns: Date, Month, Description, Amount (€), Category, Card, Notes."""
    return _read("Transactions", header_row=4)


def bank() -> pd.DataFrame:
    return _read("Bank", header_row=4)


def investments_tr() -> pd.DataFrame:
    return _read("Investments_TR", header_row=4)


def investments_crypto() -> pd.DataFrame:
    return _read("Investments_Crypto", header_row=4)


def net_worth() -> pd.DataFrame:
    return _read("Net_Worth", header_row=4)


def income_vs_expenses() -> pd.DataFrame:
    return _read("Income_vs_Expenses", header_row=4)


def source_mtime() -> str | None:
    """Last-modified timestamp of the tracker file, for footer display."""
    from datetime import datetime
    path = Path(FINANCE_TRACKER_FILE)
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
