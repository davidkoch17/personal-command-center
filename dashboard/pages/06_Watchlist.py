"""Watchlist page (phase 3)."""
from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from modules.finance import watchlist
from modules.integrations import tradingview

st.set_page_config(page_title="Watchlist", layout="wide")
st.title("Watchlist")

items = watchlist.load()

# 1. Watchlist table --------------------------------------------------------
if items:
    df = pd.DataFrame(items)
    for col in ["ticker", "name", "status", "notes"]:
        if col not in df.columns:
            df[col] = ""
    st.dataframe(
        df[["ticker", "name", "status", "notes"]],
        use_container_width=True, hide_index=True,
    )
else:
    st.info("Watchlist is empty. Add your first ticker below.")

# 2. Add to watchlist form --------------------------------------------------
st.subheader("Add to watchlist")
with st.form("add_watchlist", clear_on_submit=True):
    c1, c2 = st.columns(2)
    ticker = c1.text_input("Ticker", placeholder="e.g. NKE")
    name = c2.text_input("Name", placeholder="e.g. Nike")
    status = st.selectbox("Status", watchlist.VALID_STATUSES, index=0)
    notes = st.text_area("Notes", placeholder="Why is this on the radar?")
    submitted = st.form_submit_button("Add")
    if submitted:
        try:
            watchlist.add(ticker=ticker, name=name, status=status, notes=notes)
            st.success(f"Added {ticker.strip().upper()} to watchlist.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

# 3. Per-ticker research views ----------------------------------------------
st.subheader("Research views")
st.caption("Live chart per name. News, earnings and model views — coming later.")
for it in items:
    tk = str(it.get("ticker", "")).strip().upper()
    if not tk:
        continue
    with st.expander(f"{tk} — {it.get('name', '')}".strip(" —")):
        st.write(f"**Status:** {it.get('status', '—')}")
        st.write(f"**Notes:** {it.get('notes', '') or '—'}")
        symbol = tradingview.guess_symbol(tk)
        components.html(tradingview.mini_chart_html(symbol), height=240)
