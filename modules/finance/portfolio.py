"""Portfolio analysis from Finance_Tracker.xlsx."""
import pandas as pd
from modules.finance.loader import investments_tr, investments_crypto


def latest_snapshot_tr() -> pd.DataFrame:
    """Return only the most recent snapshot date's TR positions."""
    df = investments_tr()
    if df.empty or "Snapshot Date" not in df.columns:
        return df
    latest_date = df["Snapshot Date"].max()
    return df[df["Snapshot Date"] == latest_date].copy()


def latest_snapshot_crypto() -> pd.DataFrame:
    df = investments_crypto()
    if df.empty or "Snapshot Date" not in df.columns:
        return df
    latest_date = df["Snapshot Date"].max()
    return df[df["Snapshot Date"] == latest_date].copy()


def combined_holdings() -> pd.DataFrame:
    """Latest TR + Crypto in one frame with normalized columns."""
    tr = latest_snapshot_tr().rename(columns={"Position": "Name"})
    cr = latest_snapshot_crypto().rename(columns={"Coin": "Name"})
    cols = ["Snapshot Date", "Month", "Name", "Quantity", "Price (€)", "Value (€)", "Type", "Notes"]

    frames = []
    if not tr.empty:
        tr["Type"] = "Equity (TR)"
        frames.append(tr.reindex(columns=cols))
    if not cr.empty:
        cr["Type"] = "Crypto"
        frames.append(cr.reindex(columns=cols))
    if not frames:
        return pd.DataFrame(columns=cols)
    return pd.concat(frames, ignore_index=True)


def portfolio_value_by_month() -> pd.DataFrame:
    """Sum of values by month for TR + Crypto separately and combined."""
    tr_df = investments_tr()
    cr_df = investments_crypto()
    tr = (
        tr_df.groupby("Month")["Value (€)"].sum().rename("Trade Republic")
        if not tr_df.empty and "Month" in tr_df.columns else pd.Series(dtype="float64", name="Trade Republic")
    )
    cr = (
        cr_df.groupby("Month")["Value (€)"].sum().rename("Crypto")
        if not cr_df.empty and "Month" in cr_df.columns else pd.Series(dtype="float64", name="Crypto")
    )
    out = pd.concat([tr, cr], axis=1).fillna(0)
    if out.empty:
        return pd.DataFrame(columns=["Month", "Trade Republic", "Crypto", "Total"])
    out["Total"] = out.sum(axis=1)
    return out.sort_index().reset_index().rename(columns={"index": "Month"})


def summary_metrics() -> dict:
    h = combined_holdings()
    return {
        "total_value": float(h["Value (€)"].sum()) if not h.empty else 0.0,
        "position_count": len(h),
        "latest_snapshot": h["Snapshot Date"].max() if not h.empty else None,
    }
