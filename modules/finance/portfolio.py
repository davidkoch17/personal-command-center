"""Portfolio analysis from Finance_Tracker.xlsx."""
from __future__ import annotations

import pandas as pd

from core.config import get_logger
from modules.finance.loader import investments_tr, investments_crypto, avg_cost_column

logger = get_logger(__name__)

# Position-name → yfinance ticker. The Excel records names (e.g. "Alphabet (A)"),
# not tickers, so live prices need this mapping. Matched by case-insensitive
# substring; unmapped names fall back to "—" (no live data).
NAME_TICKER_MAP = {
    "alphabet": "GOOGL",
    "alibaba": "BABA",
    "byd": "BYDDY",
    "solana": "SOL-EUR",
    "sol": "SOL-EUR",
}


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
    """Latest TR + Crypto in one frame with normalized columns.

    Carries an "Avg Cost (€)" column when the source sheet provides one
    (see :func:`modules.finance.loader.avg_cost_column`); otherwise the column
    is present but NaN so downstream display shows "—".
    """
    tr = latest_snapshot_tr().rename(columns={"Position": "Name"})
    cr = latest_snapshot_crypto().rename(columns={"Coin": "Name"})
    cols = ["Snapshot Date", "Month", "Name", "Quantity", "Price (€)",
            "Value (€)", "Avg Cost (€)", "Type", "Notes"]

    frames = []
    if not tr.empty:
        ac = avg_cost_column(tr)
        if ac and ac != "Avg Cost (€)":
            tr = tr.rename(columns={ac: "Avg Cost (€)"})
        tr["Type"] = "Equity (TR)"
        frames.append(tr.reindex(columns=cols))
    if not cr.empty:
        ac = avg_cost_column(cr)
        if ac and ac != "Avg Cost (€)":
            cr = cr.rename(columns={ac: "Avg Cost (€)"})
        cr["Type"] = "Crypto"
        frames.append(cr.reindex(columns=cols))
    if not frames:
        return pd.DataFrame(columns=cols)
    return pd.concat(frames, ignore_index=True)


def resolve_ticker(name: str | None) -> str | None:
    """Best-effort map a holding name to a yfinance ticker (or None)."""
    n = str(name or "").lower()
    for key, tk in NAME_TICKER_MAP.items():
        if key in n:
            return tk
    return None


def _live_performance(ticker: str) -> dict:
    """Current close, year-start close, and ~1-week-ago close from yfinance.

    Returns ``{"current", "jan1", "week_ago"}`` (any value may be None on failure).
    Values are in the instrument's native currency.
    """
    out: dict = {"current": None, "jan1": None, "week_ago": None}
    try:
        import yfinance as yf

        hist = yf.Ticker(ticker).history(period="1y")
        if hist.empty:
            return out
        closes = hist["Close"].dropna()
        if closes.empty:
            return out
        out["current"] = float(closes.iloc[-1])
        year = closes.index[-1].year
        ytd = closes[closes.index.year == year]
        if not ytd.empty:
            out["jan1"] = float(ytd.iloc[0])
        out["week_ago"] = float(closes.iloc[-6]) if len(closes) >= 6 else float(closes.iloc[0])
    except Exception as exc:  # noqa: BLE001 — degrade to "—" rather than crash the table
        logger.warning("live performance failed for %s: %s", ticker, exc)
    return out


def _pct_change(current: float | None, base: float | None) -> float | None:
    if current is None or base is None or not base:
        return None
    return (current - base) / base * 100.0


def holdings_with_performance() -> pd.DataFrame:
    """Holdings table for the Portfolio overview, with live performance columns.

    Columns: Position, Ticker, Type, Quantity, Avg Cost (€), Current Price,
    Market Value (€), % Since Bought, % YTD, % Last Week. Live price / YTD /
    last-week come from yfinance per position; missing data shows as None ("—"
    in the UI). ``% Since Bought`` needs an Avg Cost (€) in the source sheet.
    """
    h = combined_holdings()
    rows: list[dict] = []
    for _, r in h.iterrows():
        name = r.get("Name")
        avg_cost = r.get("Avg Cost (€)")
        if isinstance(avg_cost, float) and pd.isna(avg_cost):
            avg_cost = None
        ticker = resolve_ticker(name)
        perf = _live_performance(ticker) if ticker else {"current": None, "jan1": None, "week_ago": None}
        current = perf["current"]
        rows.append({
            "Position": name,
            "Ticker": ticker or "—",
            "Type": "Crypto" if r.get("Type") == "Crypto" else "Equity",
            "Quantity": r.get("Quantity"),
            "Avg Cost (€)": avg_cost,
            "Current Price": current,
            "Market Value (€)": r.get("Value (€)"),
            "% Since Bought": _pct_change(current, avg_cost),
            "% YTD": _pct_change(current, perf["jan1"]),
            "% Last Week": _pct_change(current, perf["week_ago"]),
        })
    return pd.DataFrame(rows, columns=[
        "Position", "Ticker", "Type", "Quantity", "Avg Cost (€)", "Current Price",
        "Market Value (€)", "% Since Bought", "% YTD", "% Last Week",
    ])


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
