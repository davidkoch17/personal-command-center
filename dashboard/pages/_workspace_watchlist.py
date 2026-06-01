"""Per-ticker Watchlist workspace (hidden, new-tab) — Phase 9b.

URL: ``/workspace_watchlist?id=<TICKER>``. 11-section research dossier with the
Phase 5 reviewers plus the new filing/comp/thesis skills. Info-barrier locks
research actions (add hypothesis, build model) on restricted names.
"""
from __future__ import annotations

import os

import streamlit as st
import streamlit.components.v1 as components

from dashboard._theme import inject_theme, inject_shortcuts
from dashboard._skillrun import run_skill
from dashboard import _infobarrier
from core import config
from modules.finance import watchlist
from modules.agents import data_sources
from modules.investing import research
from modules.integrations import tradingview

WL_SKILLS = "modules.agents.skills.watchlist_skills"

st.set_page_config(page_title="Command Center", layout="wide")
inject_theme()
inject_shortcuts()

raw = st.query_params.get("id")
if not raw:
    st.title("Watchlist Workspace")
    st.info("Open a ticker from the Watchlist page, or pick one:")
    items = watchlist.load()
    tickers = [str(i.get("ticker", "")).upper() for i in items]
    chosen = st.selectbox("Ticker", tickers) if tickers else st.text_input("Ticker")
    if st.button("Open") and chosen:
        st.query_params["id"] = chosen
        st.rerun()
    st.stop()

ticker = raw.upper()
items = watchlist.load()
item = next((i for i in items if str(i.get("ticker", "")).upper() == ticker), {})
name = item.get("name", "")

st.title(f"{ticker} — {name}" if name else ticker)
_infobarrier.global_banner()
restricted = _infobarrier.restricted_notice(ticker)

# --- Section 1: Status + position -------------------------------------------
with st.container(border=True):
    st.subheader("1 · Status + position")
    snap = data_sources.price_snapshot(ticker)
    c1, c2, c3 = st.columns(3)
    if "error" not in snap:
        c1.metric("Last close", f"{snap.get('currency','')} {snap.get('last_close', 0):,.2f}")
        c2.metric("1w change", f"{snap.get('week_change_pct', 0):+.1f}%")
        c3.metric("30d change", f"{snap.get('month_change_pct', 0):+.1f}%")
    st.caption(f"Status: {item.get('status', '—')} · Tier: {item.get('tier', '—')} · "
               f"On watch since: {item.get('added', '—')}")
    if item.get("notes"):
        st.caption(f"Rationale: {item['notes']}")

# --- Section 2: Active hypotheses -------------------------------------------
with st.container(border=True):
    st.subheader("2 · Active hypotheses")
    hyps = research.filter_hypotheses(ticker, name)
    if hyps:
        for h in hyps:
            st.markdown(h)
    else:
        st.caption("No hypotheses reference this name yet.")
    st.markdown("**Add hypothesis**")
    hyp_text = st.text_input("Hypothesis", key="wl_hyp_text", label_visibility="collapsed")
    if restricted:
        st.button("Add hypothesis (locked)", disabled=True, key="wl_hyp_locked")
    else:
        run_skill("Add hypothesis", "modules.finance.portfolio_skills", "add_hypothesis",
                  [ticker, hyp_text], key="wl_hyp", synchronous=True)

# --- Section 3: Chart -------------------------------------------------------
with st.container(border=True):
    st.subheader("3 · Chart")
    components.html(tradingview.mini_chart_html(tradingview.guess_symbol(ticker)), height=260)

# --- Section 4: News feed ---------------------------------------------------
with st.container(border=True):
    st.subheader("4 · News")
    if st.button("Load news", key="wl_ws_news_btn"):
        st.session_state["wl_ws_news"] = data_sources.combined_news(ticker, limit=20)
    for n in st.session_state.get("wl_ws_news", []):
        link = n.get("link", "")
        title = n.get("title", "")
        st.markdown(f"- [{title}]({link})" if link else f"- {title}")

# --- Section 5: Filings -----------------------------------------------------
with st.container(border=True):
    st.subheader("5 · Filings")
    if st.button("Load filings", key="wl_ws_filings_btn"):
        st.session_state["wl_ws_filings"] = data_sources.sec_filings(ticker)
    for f in st.session_state.get("wl_ws_filings", []):
        st.caption(f.get("note") or str(f))
    st.markdown("**Summarize a filing** (paste its URL):")
    filing_url = st.text_input("Filing URL", key="wl_filing_url", label_visibility="collapsed")
    run_skill("Summarize filing", WL_SKILLS, "summarize_filing", [ticker, filing_url], key="wl_sumfile")

# --- Section 6: Comparables -------------------------------------------------
with st.container(border=True):
    st.subheader("6 · Comparables")
    peers = st.text_input("Peers (comma/space separated)", key="wl_peers")
    run_skill("Compare to peers", WL_SKILLS, "compare_to_peers", [ticker, peers], key="wl_comp")

# --- Section 7: Recent agent signals ----------------------------------------
with st.container(border=True):
    st.subheader("7 · Recent agent signals")
    sigs = research.recent_signals(ticker, name, limit=8)
    if sigs:
        for s in sigs:
            st.markdown(f"**{s['brief']}**")
            for ln in s["lines"]:
                st.caption(ln)
    else:
        st.caption("No signals in recent briefs.")

# --- Section 8: Research notes ----------------------------------------------
with st.container(border=True):
    st.subheader("8 · Research notes")
    note = research.read_position_note(ticker)
    edited = st.text_area("Notes", value=note, height=180, key="wl_note", label_visibility="collapsed")
    if st.button("Save notes", key="wl_note_save"):
        research.write_position_note(ticker, edited)
        st.toast("Saved notes")

# --- Section 9: My model ----------------------------------------------------
with st.container(border=True):
    st.subheader("9 · My model")
    note_path = research.position_note_path(ticker)
    model_path = note_path.parent / f"{ticker}_Model.xlsx"
    if model_path.exists():
        st.caption(f"Model present: {model_path.name}")
        if st.button("Open model in OS", key="wl_open_model"):
            try:
                os.startfile(str(model_path))  # noqa: S606
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not open: {exc}")
    else:
        st.caption(f"No model yet (expected at {model_path.name}).")
    st.markdown("**Build a model** (generates a spec to build in Excel):")
    assumptions = st.text_input("Key assumptions", key="wl_model_assumptions")
    if restricted:
        st.button("Build model (locked)", disabled=True, key="wl_model_locked")
    else:
        run_skill("Build model", "modules.agents.skills.model_builder", "build",
                  [ticker, "(see notes / filings)", assumptions], key="wl_model")

# --- Section 10: Decision log filtered --------------------------------------
with st.container(border=True):
    st.subheader("10 · Decisions")
    decs = research.filter_decisions(ticker, name)
    if decs:
        for head, body in decs:
            with st.expander(head, expanded=False):
                st.markdown(body or "_(empty)_")
    else:
        st.caption("No decisions reference this name.")

# --- Section 11: Skills + Ask -----------------------------------------------
with st.container(border=True):
    st.subheader("11 · Skills & Ask")
    s1, s2 = st.columns(2)
    with s1:
        run_skill("Run earnings review", "modules.agents.skills.earnings_reviewer",
                  "review", [ticker], key="wl_earn")
        run_skill("Generate thesis statement", WL_SKILLS, "generate_thesis_statement",
                  [ticker, name], key="wl_thesis")
    with s2:
        st.markdown("**Valuation review**")
        val_summary = st.text_area("Your valuation summary", height=100, key="wl_val_summary",
                                   label_visibility="collapsed")
        val_peers = st.text_input("Peers", key="wl_val_peers")
        run_skill("Run valuation review", "modules.agents.skills.valuation_reviewer", "review",
                  [ticker, val_summary, [p.strip() for p in val_peers.replace(",", " ").split() if p.strip()]],
                  key="wl_val")
