"""Watchlist — overview (Phase 9b).

Per locked design §#7: an "+ Add to watchlist" form, a Tier filter strip, and
horizontal-slicing tabs (Cards · All Hypotheses · All News · All Filings · Recent
Signals · Macro Pulse · Comp Tables). Per-ticker dossiers open in a new tab
(`_workspace_watchlist.py?id=<TICKER>`). Info-barrier locks research when active.
"""
from __future__ import annotations

from datetime import date

import streamlit as st
import streamlit.components.v1 as components

from dashboard._theme import inject_theme, inject_shortcuts
from dashboard._workspace_link import workspace_link
from dashboard._skillrun import run_skill
from dashboard import _infobarrier
from modules.finance import watchlist
from modules.agents import data_sources
from modules.investing import research
from modules.integrations import tradingview

st.set_page_config(page_title="Watchlist", layout="wide")
inject_theme()
inject_shortcuts()
st.title("Watchlist")
_infobarrier.global_banner()

# Tier-1 macro instruments (TradingView symbols) for the Macro Pulse tab.
MACRO = [
    ("S&P 500", "SP:SPX"), ("Nasdaq 100", "NASDAQ:NDX"), ("DAX", "XETR:DAX"),
    ("Hang Seng Tech", "HSI:HSTECH"), ("US 10Y", "TVC:US10Y"),
    ("EUR/USD", "FX:EURUSD"), ("VIX", "TVC:VIX"), ("Bitcoin", "BINANCE:BTCEUR"),
]


@st.cache_data(ttl=900)
def _snap(ticker: str) -> dict:
    return data_sources.price_snapshot(ticker)


items = watchlist.load()

# --- + Add to watchlist -----------------------------------------------------
with st.expander("➕ Add to watchlist", expanded=False):
    with st.form("add_watchlist", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        ticker = c1.text_input("Ticker", placeholder="e.g. NKE")
        name = c2.text_input("Name", placeholder="e.g. Nike")
        tier = c3.selectbox("Tier", ["Tier 1", "Tier 2", "Tier 3"], index=2)
        status = st.selectbox("Conviction status", watchlist.VALID_STATUSES, index=0)
        notes = st.text_area("Rationale", placeholder="Why is this on the radar?")
        if st.form_submit_button("Add"):
            try:
                new_items = watchlist.add(ticker=ticker, name=name, status=status, notes=notes)
                # Annotate tier + added-date on the just-added entry, then persist.
                tk = ticker.strip().upper()
                for it in new_items:
                    if str(it.get("ticker", "")).upper() == tk:
                        it["tier"] = tier
                        it.setdefault("added", date.today().isoformat())
                watchlist._save(new_items)
                st.success(f"Added {tk}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

# --- Tier filter strip ------------------------------------------------------
tier_filter = st.radio("Filter", ["All", "Tier 1", "Tier 2", "Tier 3"], horizontal=True)
shown = items if tier_filter == "All" else [i for i in items if i.get("tier") == tier_filter]

tabs = st.tabs([
    "Cards", "All Hypotheses", "All News", "All Filings", "Recent Signals",
    "Macro Pulse", "Comp Tables",
])

# --- Tab 1: Cards -----------------------------------------------------------
with tabs[0]:
    if not shown:
        st.info("No names in this tier. Add one above.")
    cols = st.columns(3)
    for i, it in enumerate(shown):
        tk = str(it.get("ticker", "")).upper()
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{tk}** — {it.get('name', '')}")
                snap = _snap(tk)
                if "error" not in snap:
                    st.caption(f"{snap.get('currency','')} {snap.get('last_close', 0):,.2f} · "
                               f"1w {snap.get('week_change_pct', 0):+.1f}%")
                else:
                    st.caption("price n/a")
                st.caption(f"Status: {it.get('status', '—')} · {it.get('tier', '—')}")
                added = it.get("added")
                if added:
                    st.caption(f"On watch since {added}")
                hyps = research.filter_hypotheses(tk, it.get("name", ""))
                sigs = research.recent_signals(tk, it.get("name", ""), limit=4)
                st.caption(f"{len(hyps)} hypotheses · last signal: "
                           f"{sigs[0]['brief'] if sigs else '—'}")
                workspace_link("Open Workspace ↗", "watchlist", tk)

# --- Tab 2: All Hypotheses --------------------------------------------------
with tabs[1]:
    st.caption("Active hypotheses across the watchlist, grouped by ticker.")
    any_h = False
    for it in shown:
        tk = str(it.get("ticker", "")).upper()
        hyps = research.filter_hypotheses(tk, it.get("name", ""))
        if hyps:
            any_h = True
            with st.expander(f"{tk} — {len(hyps)} hypothesis blocks", expanded=False):
                for h in hyps:
                    st.markdown(h)
    if not any_h:
        st.caption("No hypotheses reference these names yet.")

# --- Tab 3: All News --------------------------------------------------------
with tabs[2]:
    st.caption("Recent headlines per name (yfinance + Alpha Vantage, deduped).")
    if st.button("Load news for shown names", key="wl_news_btn"):
        st.session_state["wl_news"] = {
            str(it.get("ticker", "")).upper(): data_sources.combined_news(str(it.get("ticker", "")).upper(), limit=6)
            for it in shown
        }
    for tk, news in st.session_state.get("wl_news", {}).items():
        with st.expander(f"{tk} — {len(news)} headlines", expanded=False):
            for n in news:
                link = n.get("link", "")
                title = n.get("title", "")
                st.markdown(f"- [{title}]({link})" if link else f"- {title}")

# --- Tab 4: All Filings -----------------------------------------------------
with tabs[3]:
    st.caption("Recent SEC filings per name (EDGAR).")
    if st.button("Load filings for shown names", key="wl_filings_btn"):
        st.session_state["wl_filings"] = {
            str(it.get("ticker", "")).upper(): data_sources.sec_filings(str(it.get("ticker", "")).upper())
            for it in shown
        }
    for tk, filings in st.session_state.get("wl_filings", {}).items():
        with st.expander(f"{tk}", expanded=False):
            for f in filings:
                st.caption(f.get("note") or str(f))

# --- Tab 5: Recent Signals --------------------------------------------------
with tabs[4]:
    st.caption("Consolidated mentions from recent Market Briefs.")
    any_s = False
    for it in shown:
        tk = str(it.get("ticker", "")).upper()
        sigs = research.recent_signals(tk, it.get("name", ""), limit=8)
        if sigs:
            any_s = True
            with st.expander(f"{tk}", expanded=False):
                for s in sigs:
                    st.markdown(f"**{s['brief']}**")
                    for ln in s["lines"]:
                        st.caption(ln)
    if not any_s:
        st.caption("No signals for these names in recent briefs.")

# --- Tab 6: Macro Pulse -----------------------------------------------------
with tabs[5]:
    st.caption("Tier-1 macro instruments at a glance.")
    cols = st.columns(2)
    for i, (label, sym) in enumerate(MACRO):
        with cols[i % 2]:
            st.markdown(f"**{label}**")
            components.html(tradingview.mini_chart_html(sym), height=200)

# --- Tab 7: Comp Tables -----------------------------------------------------
with tabs[6]:
    st.caption("Consolidated multiples appear here once per-ticker models exist. "
               "Run an ad-hoc comp below.")
    base = st.text_input("Ticker", key="wl_comp_ticker")
    peers = st.text_input("Peers (comma/space separated)", key="wl_comp_peers")
    run_skill("Compare to peers", "modules.agents.skills.watchlist_skills",
              "compare_to_peers", [base, peers], key="wl_comp")
