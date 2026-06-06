"""Money / cash / expense analysis from Finance_Tracker.xlsx."""
import pandas as pd
from modules.finance.loader import transactions, bank, net_worth, income_vs_expenses


def transactions_normalized() -> pd.DataFrame:
    df = transactions()
    if df.empty:
        return df
    # Ensure types
    if "Amount (€)" in df.columns:
        df["Amount (€)"] = pd.to_numeric(df["Amount (€)"], errors="coerce")
    return df.dropna(subset=["Date", "Amount (€)"]) if "Date" in df.columns else df


def monthly_spending_by_category() -> pd.DataFrame:
    df = transactions_normalized()
    if df.empty or "Category" not in df.columns or "Month" not in df.columns:
        return pd.DataFrame()
    return df.pivot_table(index="Month", columns="Category", values="Amount (€)", aggfunc="sum").fillna(0)


def current_cash_balance() -> float | None:
    """Latest non-zero Ending Balance from Bank sheet.

    Only real ``YYYY-MM`` month rows count — the sheet's trailing summary row
    (e.g. "12-mo Total") would otherwise be picked up as the "latest" balance.
    """
    b = bank()
    if b.empty or "Ending Balance (€)" not in b.columns:
        return None
    if "Month" in b.columns:
        b = b[b["Month"].astype(str).str.match(r"^\d{4}-\d{2}$")]
    valid = b.dropna(subset=["Ending Balance (€)"])
    valid = valid[valid["Ending Balance (€)"] != 0]
    if valid.empty:
        return None
    return float(valid.iloc[-1]["Ending Balance (€)"])


def latest_net_worth() -> dict:
    nw = net_worth()
    if nw.empty:
        return {"month": None, "total": None, "bank": None, "tr": None, "crypto": None}
    latest = nw.iloc[-1]
    return {
        "month": latest.get("Month"),
        "total": latest.get("Total Net Worth (€)"),
        "bank": latest.get("Bank Balance (€)"),
        "tr": latest.get("Trade Republic (€)"),
        "crypto": latest.get("Crypto (€)"),
    }


def monthly_totals() -> pd.DataFrame:
    """Income, expenses, savings per month from Income_vs_Expenses sheet."""
    ive = income_vs_expenses()
    # IvE sheet is wide format — months across columns. Need to identify month columns.
    if ive.empty:
        return pd.DataFrame()
    month_cols = [c for c in ive.columns if isinstance(c, str) and c.startswith("2025-") or (isinstance(c, str) and c.startswith("2026-"))]
    # Find rows: Total Income, Total Expenses (the sheet has these labels in the 'Item' column).
    item_col = ive.columns[0] if "Item" not in ive.columns else "Item"
    out = []
    for label, key in [("Total Income", "income"), ("Total Expenses", "expenses"), ("Net Savings", "savings")]:
        row = ive[ive[item_col].astype(str).str.strip() == label]
        if not row.empty:
            for m in month_cols:
                val = row.iloc[0].get(m)
                if pd.notna(val):
                    out.append({"month": m, key: float(val)})
    # pivot into wide form
    if not out:
        return pd.DataFrame()
    df = pd.DataFrame(out)
    return df.groupby("month").first().reset_index()


def monthly_fixed_estimate() -> float | None:
    """Average of 'fixed' categories (Rent, Subscriptions, Utilities) over last 3 months."""
    df = transactions_normalized()
    if df.empty:
        return None
    fixed_cats = {"Rent", "Subscriptions", "Utilities"}
    fixed = df[df["Category"].isin(fixed_cats)]
    if fixed.empty:
        return None
    monthly = fixed.groupby("Month")["Amount (€)"].sum()
    # Average of last 3 months that have data
    return float(monthly.tail(3).mean()) if len(monthly) >= 1 else None


def runway_months(cash: float | None, monthly_fixed: float | None) -> float | None:
    if cash is None or monthly_fixed is None or monthly_fixed == 0:
        return None
    return cash / monthly_fixed
