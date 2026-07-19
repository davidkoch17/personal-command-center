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
    """Compute net worth from raw investment sheets (bypasses stale formula cache).

    Falls back to the Net_Worth summary sheet only when raw sheets are unavailable.
    Raw computation is preferred because openpyxl writes don't recalculate formulas,
    leaving the Net_Worth sheet's cached totals stale after Python updates.
    """
    from modules.finance.loader import investments_tr, investments_crypto

    # Determine current month from the Bank sheet
    b = bank()
    current_month: str | None = None
    if not b.empty and "Month" in b.columns:
        valid = b[b["Month"].astype(str).str.match(r"^\d{4}-\d{2}$")]["Month"].dropna()
        if not valid.empty:
            current_month = str(valid.iloc[-1])

    # Cash (bank ending balance)
    bank_val = current_cash_balance()

    # Trade Republic — sum all rows for the latest snapshot month
    tr_total: float | None = None
    try:
        tr_df = investments_tr()
        if not tr_df.empty and "Month" in tr_df.columns and "Value (€)" in tr_df.columns:
            snap_month = current_month
            if snap_month is None:
                # use most recent month present in TR sheet
                months = tr_df["Month"].astype(str).str.strip()
                months = months[months.str.match(r"^\d{4}-\d{2}$")]
                if not months.empty:
                    snap_month = sorted(months.unique())[-1]
            if snap_month:
                rows = tr_df[tr_df["Month"].astype(str).str.strip() == snap_month]
                vals = pd.to_numeric(rows["Value (€)"], errors="coerce").dropna()
                if not vals.empty:
                    tr_total = round(float(vals.sum()), 2)
    except Exception:  # noqa: BLE001
        pass

    # Crypto — sum all rows for the latest snapshot month
    crypto_total: float | None = None
    try:
        cr_df = investments_crypto()
        if not cr_df.empty and "Month" in cr_df.columns and "Value (€)" in cr_df.columns:
            snap_month = current_month
            if snap_month is None:
                months = cr_df["Month"].astype(str).str.strip()
                months = months[months.str.match(r"^\d{4}-\d{2}$")]
                if not months.empty:
                    snap_month = sorted(months.unique())[-1]
            if snap_month:
                rows = cr_df[cr_df["Month"].astype(str).str.strip() == snap_month]
                vals = pd.to_numeric(rows["Value (€)"], errors="coerce").dropna()
                if not vals.empty:
                    crypto_total = round(float(vals.sum()), 2)
    except Exception:  # noqa: BLE001
        pass

    total: float | None = None
    if any(v is not None for v in (bank_val, tr_total, crypto_total)):
        total = round((bank_val or 0) + (tr_total or 0) + (crypto_total or 0), 2)

    if total is not None:
        return {
            "month": current_month,
            "total": total,
            "bank": bank_val,
            "tr": tr_total,
            "crypto": crypto_total,
        }

    # Last resort: formula-sheet cached values
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


def available_months() -> list[str]:
    """Sorted list of months that have transaction data."""
    df = transactions_normalized()
    if df.empty or "Month" not in df.columns:
        return []
    months = sorted(df["Month"].dropna().astype(str).unique().tolist())
    return months


def monthly_income(month: str) -> dict:
    """Salary + other income for a given month from the Bank sheet."""
    b = bank()
    if b.empty:
        return {"salary": 0.0, "other": 0.0, "total": 0.0}
    b = b[b["Month"].astype(str).str.match(r"^\d{4}-\d{2}$")]
    row = b[b["Month"].astype(str) == month]
    if row.empty:
        return {"salary": 0.0, "other": 0.0, "total": 0.0}
    r = row.iloc[0]
    salary = float(r.get("Salary In (€)", 0) or 0)
    other = float(r.get("Other Income (€)", 0) or 0)
    return {"salary": salary, "other": other, "total": round(salary + other, 2)}


def monthly_expenses_by_category(month: str) -> list[dict]:
    """Expense totals per category for a given month, sorted descending."""
    df = transactions_normalized()
    if df.empty or "Month" not in df.columns:
        return []
    sub = df[df["Month"].astype(str) == month]
    if sub.empty or "Category" not in sub.columns:
        return []
    grouped = (
        sub.groupby("Category")["Amount (€)"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    return [
        {"category": row["Category"], "amount": round(float(row["Amount (€)"]), 2)}
        for _, row in grouped.iterrows()
    ]


def monthly_transactions(month: str) -> list[dict]:
    """All individual transactions for a given month, sorted by date."""
    df = transactions_normalized()
    if df.empty or "Month" not in df.columns:
        return []
    sub = df[df["Month"].astype(str) == month].copy()
    if sub.empty:
        return []
    sub = sub.sort_values("Date")
    rows = []
    for _, r in sub.iterrows():
        date_val = r.get("Date")
        date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val)[:10]
        rows.append({
            "date": date_str,
            "description": str(r.get("Description", "") or ""),
            "amount": round(float(r.get("Amount (€)", 0) or 0), 2),
            "category": str(r.get("Category", "") or ""),
            "card": str(r.get("Card", "") or ""),
            "notes": str(r.get("Notes", "") or ""),
        })
    return rows
