"""Money — cash / spending / runway overview (Phase 9a, split from Portfolio).

Read-on-click overview per the locked design (`Phase_9_Deep_Dive_Designs.md` §#2):
four headline metrics, income-vs-expenses (last 6 months), last month's spending
breakdown, and known big upcoming outflows. The deep-dive Money workspace (Tabs:
Cash Flow / Categories / Net Worth / Forecast / Budget / Tax / Transactions) is
built in Phase 9b — the "Open Workspace ↗" button points at its placeholder.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from dashboard._charts import styled_pie
from dashboard._workspace_link import workspace_link
from core import vault
from core.config import SYSTEM_PATH
from modules.finance import loader, money
from modules.integrations import travel

st.set_page_config(page_title="Money", layout="wide")
inject_theme()
inject_shortcuts()

PLOTLY_TEMPLATE = "plotly_dark"
EMERALD_SEQUENCE = ["#10B981", "#047857", "#34D399", "#065F46", "#6EE7B7", "#059669"]
TASKS_PATH = SYSTEM_PATH / "Task_Command_Center.md"


def euro(value) -> str:
    """Format a number as euros, or an em-dash when missing."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        return f"€{float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _upcoming_task_outflows(days: int = 30) -> list[str]:
    """Unchecked task bullets carrying an ISO date within ``days`` (likely bills)."""
    md = vault.read_md(TASKS_PATH)
    if not md:
        return []
    today = date.today()
    horizon = today + timedelta(days=days)
    out: list[str] = []
    for line in md.split("\n"):
        s = line.strip()
        if not s.startswith("- [") or "[x]" in s.lower():
            continue
        for m in re.finditer(r"(\d{4})-(\d{2})-(\d{2})", s):
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
            if today <= d <= horizon:
                text = re.sub(r"^- \[[ xX]\]\s*", "", s)
                out.append(f"{d.isoformat()} — {text}")
                break
    return out


# ---------------------------------------------------------------------------
st.title("Money")
st.caption("Where the cash goes. Scan here; the deep-dive workspace opens in a new tab.")

cash = money.current_cash_balance()
nw = money.latest_net_worth()
fixed = money.monthly_fixed_estimate()
runway = money.runway_months(cash, fixed)

# 1. Headline metrics --------------------------------------------------------
m1, m2, m3, m4 = st.columns(4)
m1.metric("Cash balance", euro(cash))
m2.metric("Net worth", euro(nw.get("total")))
m3.metric("Monthly burn", euro(fixed))
m4.metric("Runway", "—" if runway is None else f"{runway:.1f} mo")

workspace_link("Open Workspace ↗", "money")
st.write("")

# 2. Income vs Expenses (last 6 months) --------------------------------------
with st.container(border=True):
    st.subheader("Income vs Expenses — last 6 months")
    totals = money.monthly_totals()
    if totals.empty or not {"income", "expenses"}.issubset(totals.columns):
        st.info("Data not available — fill Income_vs_Expenses in the Excel.")
    else:
        recent = totals.sort_values("month").tail(6)
        value_vars = [c for c in ["income", "expenses"] if c in recent.columns]
        long = recent.melt(id_vars="month", value_vars=value_vars,
                           var_name="Type", value_name="Amount (€)")
        long["Type"] = long["Type"].map({"income": "Income", "expenses": "Expenses"})
        fig = px.bar(
            long, x="month", y="Amount (€)", color="Type", barmode="group",
            template=PLOTLY_TEMPLATE, color_discrete_sequence=EMERALD_SEQUENCE,
        )
        if "savings" in recent.columns:
            fig.add_scatter(
                x=recent["month"], y=recent["savings"], mode="lines+markers",
                name="Net savings", line=dict(color="#FBBF24"),
            )
        fig.update_layout(margin=dict(t=10, b=0, l=0, r=0), height=320, xaxis_title="Month")
        st.plotly_chart(fig, use_container_width=True)

# 3. Spending breakdown (last month) -----------------------------------------
with st.container(border=True):
    st.subheader("Spending breakdown — last month")
    pivot = money.monthly_spending_by_category()
    if pivot.empty:
        st.info("Data not available — add categorized transactions in the Excel.")
    else:
        last = pivot.iloc[-1]
        last = last[last != 0].sort_values(ascending=False)
        if last.empty:
            st.caption("No categorized spending in the latest month.")
        else:
            month_label = str(pivot.index[-1])
            cat_df = last.reset_index()
            cat_df.columns = ["Category", "Amount (€)"]
            c_pie, c_top = st.columns([2, 1])
            with c_pie:
                fig = styled_pie(cat_df, names="Category", values="Amount (€)")
                fig.update_traces(hole=0.45)
                fig.update_layout(margin=dict(t=10, b=0, l=0, r=0), height=300,
                                  title=f"{month_label}")
                st.plotly_chart(fig, use_container_width=True)
            with c_top:
                st.markdown("**Top 3 categories**")
                for cat, amt in last.head(3).items():
                    st.metric(str(cat), euro(amt))

# 4. Big upcoming (next 30 days) ---------------------------------------------
with st.container(border=True):
    st.subheader("Big upcoming — next 30 days")
    rows = _upcoming_task_outflows(30)
    trips = travel.upcoming_trips()
    trip_rows: list[str] = []
    for t in trips:
        dleft = travel.days_until(t["date"])
        if dleft is not None and 0 <= dleft <= 30:
            trip_rows.append(f"{t['date']} — Travel: {t['destination']} (in {dleft}d)")
    if not rows and not trip_rows:
        st.caption("Nothing flagged in Tasks or Travel for the next 30 days.")
    else:
        for r in rows:
            st.markdown(f"- 💳 {r}")
        for r in trip_rows:
            st.markdown(f"- ✈️ {r}")

st.caption(f"Source: Finance_Tracker.xlsx. Last modified: {loader.source_mtime() or 'n/a'}.")
