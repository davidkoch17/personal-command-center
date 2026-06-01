"""Portfolio — overview (Phase 9b, holdings table redo in Phase 10a).

Read-on-click glance per locked design §#1: headline metrics, a clean holdings
table with live performance, latest Market-Brief signals, and "Open Workspace ↗".
The deep-dive (7 tabs + per-holding sub-view) lives in the new-tab workspace
`_workspace_portfolio.py`.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from dashboard._workspace_link import workspace_link
from dashboard import _infobarrier
from core.config import MARKET_BRIEFS_DIR
from modules.finance import portfolio, money

st.set_page_config(page_title="Command Center", layout="wide")
inject_theme()
inject_shortcuts()

_SUCCESS = "#10B981"
_DANGER = "#EF4444"


def euro(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        return f"€ {float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def pct(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        return f"{float(value):+.2f} %"
    except (TypeError, ValueError):
        return "—"


def qty(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        return f"{float(value):,.4f}"
    except (TypeError, ValueError):
        return "—"


def _color_pct(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        return f"color: {_SUCCESS}" if float(value) >= 0 else f"color: {_DANGER}"
    except (TypeError, ValueError):
        return ""


@st.cache_data(ttl=900)
def _holdings_table() -> pd.DataFrame:
    """Cached so the per-position yfinance calls don't re-run on every rerun."""
    return portfolio.holdings_with_performance()


@st.cache_data(ttl=900)
def _latest_brief_text() -> str:
    if not MARKET_BRIEFS_DIR.exists():
        return ""
    briefs = sorted(MARKET_BRIEFS_DIR.glob("*.md"), reverse=True)
    return briefs[0].read_text(encoding="utf-8") if briefs else ""


st.title("Portfolio")
_infobarrier.global_banner()

hp = _holdings_table()
metrics = portfolio.summary_metrics()
cash = money.current_cash_balance()
total_value = metrics["total_value"]

# Cost basis / P&L from Avg Cost (€) where the sheet provides it.
cost_basis = 0.0
have_cost = False
for _, r in hp.iterrows():
    ac, q = r["Avg Cost (€)"], r["Quantity"]
    if ac is not None and not pd.isna(ac) and q is not None and not pd.isna(q):
        cost_basis += float(ac) * float(q)
        have_cost = True
pnl_eur = (total_value - cost_basis) if have_cost else None
pnl_pct = (pnl_eur / cost_basis * 100.0) if (have_cost and cost_basis) else None

# 1. Top metrics --------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total value", euro(total_value))
c2.metric("Total P&L (€)", euro(pnl_eur))
c3.metric("Total P&L (%)", pct(pnl_pct))
c4.metric("Cash deployable", euro(cash))

workspace_link("Open Workspace ↗", "portfolio")
st.write("")

# 2. Holdings table (the main view) ------------------------------------------
with st.container(border=True):
    st.subheader("Holdings")
    if hp.empty:
        st.caption("No holdings in the latest snapshot.")
    else:
        styler = (
            hp.style
            .format({
                "Quantity": qty,
                "Avg Cost (€)": euro,
                "Current Price": euro,
                "Market Value (€)": euro,
                "% Since Bought": pct,
                "% YTD": pct,
                "% Last Week": pct,
            })
            .map(_color_pct, subset=["% Since Bought", "% YTD", "% Last Week"])
        )
        st.dataframe(styler, use_container_width=True, hide_index=True)
    st.caption(
        "Live price / YTD / last-week from yfinance in the instrument's native "
        "currency. Avg Cost (€) and % Since Bought populate once an \"Avg Cost (€)\" "
        "column exists in the tracker. "
        f"Latest snapshot: {metrics['latest_snapshot']} · {metrics['position_count']} positions."
    )

# 3. Signals (latest Market Brief) -------------------------------------------
with st.container(border=True):
    st.subheader("Signals — latest Market Brief")
    brief = _latest_brief_text()
    if not brief:
        st.caption("No Market Brief found yet.")
    else:
        held_names = [str(n) for n in hp["Position"].dropna().unique()] if not hp.empty else []
        lines = [ln.strip(" -*") for ln in brief.splitlines()
                 if ln.strip() and any(h.split()[0].lower() in ln.lower() for h in held_names)]
        if lines:
            for ln in lines[:6]:
                st.markdown(f"- {ln}")
        else:
            st.caption("No held names flagged in the latest brief.")
