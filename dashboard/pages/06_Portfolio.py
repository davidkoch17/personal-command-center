"""Portfolio — overview (Phase 9b).

Read-on-click glance per locked design §#1: headline metrics, allocation donut +
recent movers, watchlist signals from the latest Market Brief, recent activity,
and "Open Workspace ↗". The deep-dive (7 tabs + per-holding sub-view) lives in
the new-tab workspace `_workspace_portfolio.py`.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from dashboard._charts import styled_pie
from dashboard._workspace_link import workspace_link
from dashboard import _infobarrier
from core.config import MARKET_BRIEFS_DIR
from modules.finance import loader, portfolio, money

st.set_page_config(page_title="Portfolio", layout="wide")
inject_theme()
inject_shortcuts()


def euro(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        return f"€{float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


@st.cache_data(ttl=900)
def _latest_brief_text() -> str:
    if not MARKET_BRIEFS_DIR.exists():
        return ""
    briefs = sorted(MARKET_BRIEFS_DIR.glob("*.md"), reverse=True)
    return briefs[0].read_text(encoding="utf-8") if briefs else ""


st.title("Portfolio")
_infobarrier.global_banner()

holdings = portfolio.combined_holdings()
metrics = portfolio.summary_metrics()
cash = money.current_cash_balance()

# 1. Top metrics -------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total value", euro(metrics["total_value"]))
c2.metric("P&L today", "—")
c3.metric("P&L YTD", "—")
c4.metric("Cash deployable", euro(cash))
st.caption(
    "P&L today / YTD are snapshot-based here (no intraday feed wired) — use the "
    "workspace Performance tab for return analysis."
)

workspace_link("Open Workspace ↗", "portfolio")
st.write("")

# 2. Allocation + movers -----------------------------------------------------
col_alloc, col_movers = st.columns(2)
with col_alloc:
    with st.container(border=True):
        st.subheader("Allocation")
        rows = []
        if not holdings.empty:
            by_type = holdings.groupby("Type", dropna=True)["Value (€)"].sum()
            for t, v in by_type.items():
                rows.append({"Bucket": str(t), "Value (€)": float(v)})
        if cash:
            rows.append({"Bucket": "Cash", "Value (€)": float(cash)})
        if rows:
            df = pd.DataFrame(rows)
            fig = styled_pie(df, names="Bucket", values="Value (€)")
            fig.update_traces(hole=0.5)
            fig.update_layout(height=280, margin=dict(t=10, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No allocation data.")

with col_movers:
    with st.container(border=True):
        st.subheader("Top positions")
        if holdings.empty:
            st.caption("No holdings.")
        else:
            top = (holdings.groupby("Name", dropna=True)["Value (€)"].sum()
                   .sort_values(ascending=False).head(3))
            for name, val in top.items():
                st.metric(str(name), euro(val))

# 3. Watchlist signals (latest brief) ----------------------------------------
with st.container(border=True):
    st.subheader("Signals — latest Market Brief")
    brief = _latest_brief_text()
    if not brief:
        st.caption("No Market Brief found yet.")
    else:
        held_names = [str(n) for n in holdings["Name"].dropna().unique()] if not holdings.empty else []
        lines = [ln.strip(" -*") for ln in brief.splitlines()
                 if ln.strip() and any(h.split()[0].lower() in ln.lower() for h in held_names)]
        if lines:
            for ln in lines[:6]:
                st.markdown(f"- {ln}")
        else:
            st.caption("No held names flagged in the latest brief. Open the Agents page for the full brief.")

# 4. Recent activity ---------------------------------------------------------
with st.container(border=True):
    st.subheader("Recent activity")
    st.caption(f"Finance tracker last modified: {loader.source_mtime() or 'n/a'}.")
    if not holdings.empty:
        st.caption(f"Latest snapshot: {metrics['latest_snapshot']} · {metrics['position_count']} positions.")
