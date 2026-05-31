"""Portfolio + Money analysis page (phase 3, Finance_Tracker.xlsx)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from modules.finance import loader, money, portfolio
from modules.integrations import kraken, tradingview

st.set_page_config(page_title="Portfolio", layout="wide")

# Dark theme + emerald-led palette to match the dashboard.
PLOTLY_TEMPLATE = "plotly_dark"
EMERALD_SEQUENCE = ["#10B981", "#047857", "#34D399", "#065F46", "#6EE7B7", "#059669"]


def euro(value) -> str:
    """Format a number as euros, or an em-dash when missing."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        return f"€{float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


def fmt_date(value) -> str:
    """Format a date/Timestamp as YYYY-MM-DD, or em-dash."""
    if value is None or pd.isna(value):
        return "—"
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return str(value)


tab_portfolio, tab_money = st.tabs(["Portfolio", "Money"])

# ---------------------------------------------------------------------------
# TAB 1 — PORTFOLIO
# ---------------------------------------------------------------------------
with tab_portfolio:
    st.title("Portfolio")

    holdings = portfolio.combined_holdings()
    metrics = portfolio.summary_metrics()

    # 1. Top metrics -------------------------------------------------------
    c1, c2, c3 = st.columns(3)
    c1.metric("Total value", euro(metrics["total_value"]))
    c2.metric("Positions", metrics["position_count"])
    c3.metric("Latest snapshot", fmt_date(metrics["latest_snapshot"]))

    if holdings.empty:
        st.info("Data not available — fill Investments_TR / Investments_Crypto in the Excel.")
    else:
        # 2. Holdings table ------------------------------------------------
        st.subheader("Holdings")
        table = holdings.sort_values("Value (€)", ascending=False).copy()
        table["Snapshot Date"] = table["Snapshot Date"].apply(fmt_date)
        st.dataframe(
            table[["Name", "Type", "Quantity", "Price (€)", "Value (€)", "Snapshot Date"]]
            .style.format({
                "Quantity": "{:,.4f}",
                "Price (€)": lambda v: "—" if pd.isna(v) else f"€{v:,.2f}",
                "Value (€)": lambda v: "—" if pd.isna(v) else f"€{v:,.2f}",
            }),
            use_container_width=True, hide_index=True,
        )

        # 2b. Per-holding TradingView charts -------------------------------
        st.subheader("Charts")
        st.caption("Live weekly mini-charts from TradingView.")
        for name in table["Name"].dropna().unique():
            symbol = tradingview.guess_symbol(str(name))
            with st.expander(f"{name}  ·  {symbol}"):
                components.html(tradingview.mini_chart_html(symbol), height=240)

        # 3. Allocation by Type (pie) --------------------------------------
        st.subheader("Allocation by type")
        by_type = holdings.groupby("Type", dropna=True)["Value (€)"].sum().reset_index()
        fig = px.pie(
            by_type, names="Type", values="Value (€)", hole=0.45,
            template=PLOTLY_TEMPLATE, color_discrete_sequence=EMERALD_SEQUENCE,
        )
        fig.update_layout(margin=dict(t=10, b=0, l=0, r=0), height=320)
        st.plotly_chart(fig, use_container_width=True)

        # 4. Allocation by Name (horizontal bar) ---------------------------
        st.subheader("Positions by value")
        by_name = holdings.groupby("Name", dropna=True)["Value (€)"].sum().reset_index()
        by_name = by_name.sort_values("Value (€)", ascending=True)
        fig = px.bar(
            by_name, x="Value (€)", y="Name", orientation="h",
            template=PLOTLY_TEMPLATE, color_discrete_sequence=EMERALD_SEQUENCE,
        )
        fig.update_layout(margin=dict(t=10, b=0, l=0, r=0), height=max(240, 40 * len(by_name)))
        st.plotly_chart(fig, use_container_width=True)

    # 5. Portfolio value over time ----------------------------------------
    st.subheader("Portfolio value over time")
    pvm = portfolio.portfolio_value_by_month()
    if pvm.empty or pvm[["Trade Republic", "Crypto", "Total"]].sum().sum() == 0:
        st.info("Data not available — add monthly snapshots in Investments_TR / Investments_Crypto.")
    else:
        long = pvm.melt(id_vars="Month", value_vars=["Trade Republic", "Crypto", "Total"],
                        var_name="Series", value_name="Value (€)")
        fig = px.line(
            long, x="Month", y="Value (€)", color="Series", markers=True,
            template=PLOTLY_TEMPLATE, color_discrete_sequence=EMERALD_SEQUENCE,
        )
        fig.update_layout(margin=dict(t=10, b=0, l=0, r=0), height=340)
        st.plotly_chart(fig, use_container_width=True)

    # 6. Footer ------------------------------------------------------------
    st.caption(f"Source: Finance_Tracker.xlsx. Last modified: {loader.source_mtime() or 'n/a'}.")


# ---------------------------------------------------------------------------
# TAB 2 — MONEY
# ---------------------------------------------------------------------------
def _kraken_eur_pair(asset: str) -> str | None:
    """Map a Kraken asset code to its EUR ticker pair, or None for EUR/dust.

    Handles legacy 4-char codes (XXBT/XETH/ZEUR), staking suffixes (``SOL.S``),
    and the ``XBT`` alias for Bitcoin.
    """
    base = asset.split(".")[0]  # drop staking suffix, e.g. SOL.S -> SOL
    if len(base) == 4 and base[0] in ("X", "Z"):
        base = base[1:]
    if base in ("EUR", "ZEUR"):
        return None  # already EUR
    if base == "XBT":
        base = "XBT"  # Kraken uses XBT for Bitcoin
    return f"{base}EUR"


with tab_money:
    st.title("Money")

    # 0. Live crypto (Kraken) — above the Excel snapshot -------------------
    with st.container(border=True):
        st.subheader("Live crypto (Kraken)")
        if not kraken.is_configured():
            st.info("Kraken not configured. Add `KRAKEN_API_KEY` and `KRAKEN_API_SECRET` to `.env`.")
        else:
            bal = kraken.balance()
            if not bal:
                st.warning("Could not read Kraken balance (check API key permissions).")
            else:
                rows = []
                total_eur = 0.0
                for asset, amount in sorted(bal.items()):
                    if amount <= 1e-8:
                        continue
                    pair = _kraken_eur_pair(asset)
                    if pair is None:  # EUR cash
                        price, value = 1.0, amount
                    else:
                        price = kraken.ticker_price(pair)
                        value = (amount * price) if price is not None else None
                    if value is not None:
                        total_eur += value
                    rows.append({
                        "Asset": asset,
                        "Amount": amount,
                        "Price (€)": price,
                        "Value (€)": value,
                    })
                if rows:
                    df_k = pd.DataFrame(rows)
                    st.dataframe(
                        df_k.style.format({
                            "Amount": "{:,.6f}",
                            "Price (€)": lambda v: "—" if v is None or pd.isna(v) else f"€{v:,.2f}",
                            "Value (€)": lambda v: "—" if v is None or pd.isna(v) else f"€{v:,.2f}",
                        }),
                        use_container_width=True, hide_index=True,
                    )
                    st.metric("Total live crypto value", euro(total_eur))
                else:
                    st.caption("No non-zero balances.")
        st.caption("Live from Kraken. Excel snapshot below is a monthly point-in-time.")

    cash = money.current_cash_balance()
    nw = money.latest_net_worth()
    fixed = money.monthly_fixed_estimate()
    runway = money.runway_months(cash, fixed)

    # 1. Top metrics -------------------------------------------------------
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Cash balance", euro(cash))
    m2.metric("Net worth", euro(nw.get("total")))
    m3.metric("Monthly fixed (est)", euro(fixed))
    m4.metric("Runway", "—" if runway is None else f"{runway:.1f} mo")

    # 2. Income vs Expenses ------------------------------------------------
    st.subheader("Income vs Expenses")
    totals = money.monthly_totals()
    if totals.empty or not {"income", "expenses"}.issubset(totals.columns):
        st.info("Data not available — fill Income_vs_Expenses in the Excel.")
    else:
        recent = totals.sort_values("month").tail(12)
        value_vars = [c for c in ["income", "expenses"] if c in recent.columns]
        long = recent.melt(id_vars="month", value_vars=value_vars,
                           var_name="Type", value_name="Amount (€)")
        long["Type"] = long["Type"].map({"income": "Income", "expenses": "Expenses"})
        fig = px.bar(
            long, x="month", y="Amount (€)", color="Type", barmode="group",
            template=PLOTLY_TEMPLATE, color_discrete_sequence=EMERALD_SEQUENCE,
        )
        fig.update_layout(margin=dict(t=10, b=0, l=0, r=0), height=320, xaxis_title="Month")
        st.plotly_chart(fig, use_container_width=True)

    # 3. Spending by category (stacked) ------------------------------------
    st.subheader("Spending by category")
    pivot = money.monthly_spending_by_category()
    if pivot.empty:
        st.info("Data not available — add categorized transactions in the Excel.")
    else:
        recent = pivot.tail(6)
        long = recent.reset_index().melt(id_vars="Month", var_name="Category", value_name="Amount (€)")
        long = long[long["Amount (€)"] != 0]
        fig = px.bar(
            long, x="Month", y="Amount (€)", color="Category", barmode="stack",
            template=PLOTLY_TEMPLATE, color_discrete_sequence=px.colors.qualitative.Set3,
        )
        fig.update_layout(margin=dict(t=10, b=0, l=0, r=0), height=360)
        st.plotly_chart(fig, use_container_width=True)

    # 4. Recent transactions -----------------------------------------------
    st.subheader("Recent transactions")
    tx = money.transactions_normalized()
    if tx.empty:
        st.info("Data not available — add transactions in the Excel.")
    else:
        recent_tx = tx.sort_values("Date", ascending=False).head(30).copy()
        recent_tx["Date"] = recent_tx["Date"].apply(fmt_date)
        show_cols = [c for c in ["Date", "Description", "Amount (€)", "Category", "Card"] if c in recent_tx.columns]
        st.dataframe(
            recent_tx[show_cols].style.format({"Amount (€)": "€{:,.2f}"}),
            use_container_width=True, hide_index=True,
        )

    st.caption(f"Source: Finance_Tracker.xlsx. Last modified: {loader.source_mtime() or 'n/a'}.")
