"""Portfolio — investment analytics (Phase 3, Finance_Tracker.xlsx).

Phase 9a: the Money tab was split out into its own sidebar page (`07_Money.py`).
This page is investment-only. The deep-dive Portfolio workspace (Holdings /
Allocations / Performance / Attribution / Risk / Scenarios / Tax) is built in
Phase 9b — the "Open Workspace ↗" button points at its placeholder.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from dashboard._theme import inject_theme, inject_shortcuts
from dashboard._charts import styled_pie
from dashboard._workspace_link import workspace_link
from modules.finance import loader, portfolio
from modules.integrations import tradingview

st.set_page_config(page_title="Portfolio", layout="wide")
inject_theme()
inject_shortcuts()

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


st.title("Portfolio")

holdings = portfolio.combined_holdings()
metrics = portfolio.summary_metrics()

# 1. Top metrics -------------------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Total value", euro(metrics["total_value"]))
c2.metric("Positions", metrics["position_count"])
c3.metric("Latest snapshot", fmt_date(metrics["latest_snapshot"]))

workspace_link("Open Workspace ↗", "portfolio")
st.write("")

if holdings.empty:
    st.info("Data not available — fill Investments_TR / Investments_Crypto in the Excel.")
else:
    # 2. Holdings table ------------------------------------------------------
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

    # 2b. Per-holding TradingView charts -------------------------------------
    st.subheader("Charts")
    st.caption("Live weekly mini-charts from TradingView.")
    for name in table["Name"].dropna().unique():
        symbol = tradingview.guess_symbol(str(name))
        with st.expander(f"{name}  ·  {symbol}"):
            components.html(tradingview.mini_chart_html(symbol), height=240)

    # 3. Allocation by Type (pie) --------------------------------------------
    st.subheader("Allocation by type")
    by_type = holdings.groupby("Type", dropna=True)["Value (€)"].sum().reset_index()
    fig = styled_pie(by_type, names="Type", values="Value (€)")
    fig.update_traces(hole=0.45)
    fig.update_layout(margin=dict(t=10, b=0, l=0, r=0), height=320)
    st.plotly_chart(fig, use_container_width=True)

    # 4. Allocation by Name (horizontal bar) ---------------------------------
    st.subheader("Positions by value")
    by_name = holdings.groupby("Name", dropna=True)["Value (€)"].sum().reset_index()
    by_name = by_name.sort_values("Value (€)", ascending=True)
    fig = px.bar(
        by_name, x="Value (€)", y="Name", orientation="h",
        template=PLOTLY_TEMPLATE, color_discrete_sequence=EMERALD_SEQUENCE,
    )
    fig.update_layout(margin=dict(t=10, b=0, l=0, r=0), height=max(240, 40 * len(by_name)))
    st.plotly_chart(fig, use_container_width=True)

# 5. Portfolio value over time -----------------------------------------------
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

# 6. Footer ------------------------------------------------------------------
st.caption(f"Source: Finance_Tracker.xlsx. Last modified: {loader.source_mtime() or 'n/a'}.")
