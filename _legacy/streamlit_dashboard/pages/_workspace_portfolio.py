"""Portfolio workspace (hidden, new-tab) — Phase 9b.

URL: ``/workspace_portfolio``. Tabbed deep-dive (Holdings · Allocations ·
Performance · Attribution · Risk · Scenarios · Tax) with a per-holding research
sub-view. Skills run via the shared Run/background helper. Info-barrier locks
research actions on restricted names.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from dashboard._theme import inject_theme, inject_shortcuts
from dashboard._charts import styled_pie
from dashboard._skillrun import run_skill
from dashboard import _infobarrier
from core import config
from modules.finance import portfolio, money
from modules.agents import data_sources
from modules.investing import research
from modules.integrations import tradingview

st.set_page_config(page_title="Command Center", layout="wide")
inject_theme()
inject_shortcuts()

PLOTLY_TEMPLATE = "plotly_dark"
EMERALD = ["#10B981", "#047857", "#34D399", "#065F46", "#6EE7B7", "#059669"]


def euro(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        return f"€{float(v):,.0f}"
    except (TypeError, ValueError):
        return "—"


st.title("Portfolio Workspace")
_infobarrier.global_banner()

holdings = portfolio.combined_holdings()
metrics = portfolio.summary_metrics()
cash = money.current_cash_balance()

tabs = st.tabs([
    "Holdings", "Allocations", "Performance", "Attribution", "Risk", "Scenarios", "Tax",
])

# --- Tab 1: Holdings + per-holding sub-view ---------------------------------
with tabs[0]:
    if holdings.empty:
        st.info("No holdings — fill Investments_TR / Investments_Crypto in the Excel.")
    else:
        table = holdings.sort_values("Value (€)", ascending=False).copy()
        st.dataframe(
            table[["Name", "Type", "Quantity", "Price (€)", "Value (€)", "Snapshot Date"]],
            use_container_width=True, hide_index=True,
        )

        st.divider()
        st.subheader("Inspect a holding")
        names = list(table["Name"].dropna().unique())
        sel = st.selectbox("Holding", names, key="pf_holding_sel")
        if sel:
            row = table[table["Name"] == sel].iloc[0]
            st.markdown(f"### {sel}  ·  {euro(row['Value (€)'])}")
            restricted = _infobarrier.restricted_notice(sel)

            ticker = st.text_input(
                "Ticker (for news / filings / skills)",
                value=str(sel).split()[0].upper(),
                key="pf_holding_ticker",
            )

            # Embedded TradingView chart
            with st.expander("Chart", expanded=False):
                components.html(tradingview.mini_chart_html(tradingview.guess_symbol(ticker)), height=240)

            # Research notes (per-ticker, saved to vault)
            with st.container(border=True):
                st.markdown("**Research notes**")
                note = research.read_position_note(ticker)
                edited = st.text_area("Notes", value=note, height=160, key="pf_note", label_visibility="collapsed")
                if st.button("Save notes", key="pf_note_save"):
                    research.write_position_note(ticker, edited)
                    st.toast("Saved notes")

            # News
            with st.container(border=True):
                st.markdown("**News**")
                if st.button("Load news", key="pf_news_btn"):
                    st.session_state["pf_news"] = data_sources.combined_news(ticker, limit=10)
                for n in st.session_state.get("pf_news", []):
                    title = n.get("title", "")
                    link = n.get("link", "")
                    st.markdown(f"- [{title}]({link})" if link else f"- {title}")

            # Hypotheses
            with st.container(border=True):
                st.markdown("**Hypotheses**")
                hyps = research.filter_hypotheses(ticker, sel)
                if hyps:
                    for h in hyps:
                        st.markdown(h)
                else:
                    st.caption("No hypotheses reference this name yet.")

            # Filings
            with st.container(border=True):
                st.markdown("**SEC filings**")
                if st.button("Load filings", key="pf_filings_btn"):
                    st.session_state["pf_filings"] = data_sources.sec_filings(ticker)
                for f in st.session_state.get("pf_filings", []):
                    st.caption(f.get("note") or str(f))

            # Action skills
            st.markdown("**Actions**")
            ac1, ac2 = st.columns(2)
            with ac1:
                run_skill("Run earnings review", "modules.agents.skills.earnings_reviewer",
                          "review", [ticker], key="pf_earn")
                run_skill("Why is this moving?", "modules.finance.portfolio_skills",
                          "why_is_x_moving", [ticker, ""], key="pf_why")
            with ac2:
                with st.container(border=True):
                    st.caption("Add hypothesis")
                    hyp_text = st.text_input("Hypothesis", key="pf_hyp_text", label_visibility="collapsed",
                                             placeholder="e.g. moat widening on X")
                    if restricted:
                        st.button("Add hypothesis (locked)", key="pf_hyp_locked", disabled=True)
                    else:
                        run_skill("Add hypothesis", "modules.finance.portfolio_skills",
                                  "add_hypothesis", [ticker, hyp_text], key="pf_hyp",
                                  synchronous=True)

# --- Tab 2: Allocations -----------------------------------------------------
with tabs[1]:
    st.subheader("Allocation over time")
    pvm = portfolio.portfolio_value_by_month()
    if pvm.empty or pvm[["Trade Republic", "Crypto"]].sum().sum() == 0:
        st.info("Add monthly snapshots in Investments_TR / Investments_Crypto for a time series.")
    else:
        long = pvm.melt(id_vars="Month", value_vars=["Trade Republic", "Crypto"],
                        var_name="Bucket", value_name="Value (€)")
        fig = px.area(long, x="Month", y="Value (€)", color="Bucket",
                      template=PLOTLY_TEMPLATE, color_discrete_sequence=EMERALD)
        fig.update_layout(height=340, margin=dict(t=10, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)
    st.caption("Sector / region / currency breakdowns need per-holding metadata not in the Excel yet.")

# --- Tab 3: Performance -----------------------------------------------------
with tabs[2]:
    st.subheader("Performance")
    pvm = portfolio.portfolio_value_by_month()
    if not pvm.empty and "Total" in pvm.columns and len(pvm) >= 2:
        s = pvm.set_index("Month")["Total"].replace(0, pd.NA).dropna()
        if len(s) >= 2:
            chg = s.pct_change().dropna() * 100
            fig = px.bar(chg.reset_index(), x="Month", y="Total",
                         template=PLOTLY_TEMPLATE, color_discrete_sequence=EMERALD)
            fig.update_layout(height=300, margin=dict(t=10, b=0, l=0, r=0),
                              yaxis_title="MoM change %")
            st.plotly_chart(fig, use_container_width=True)
            c1, c2 = st.columns(2)
            c1.metric("Best month", f"{chg.max():.1f}%")
            c2.metric("Worst month", f"{chg.min():.1f}%")
        else:
            st.info("Not enough monthly snapshots for a return series.")
    else:
        st.info("Not enough monthly snapshots for a return series.")
    st.divider()
    st.caption("Generate a full written review (benchmarks, hypotheses, risk):")
    run_skill("Quarterly portfolio review", "modules.finance.portfolio_skills",
              "quarterly_portfolio_review", [], key="pf_qreview")

# --- Tab 4: Attribution -----------------------------------------------------
with tabs[3]:
    st.subheader("Attribution")
    if holdings.empty:
        st.info("No holdings.")
    else:
        by_name = holdings.groupby("Name", dropna=True)["Value (€)"].sum().sort_values(ascending=False)
        st.markdown("**Largest positions (value contribution)**")
        for name, val in by_name.head(5).items():
            st.markdown(f"- {name}: {euro(val)}")
    st.caption("Period-over-period contributor/detractor attribution needs lot-level history "
               "(buys/sells) not in the snapshot Excel. The quarterly review skill covers this qualitatively.")

# --- Tab 5: Risk ------------------------------------------------------------
with tabs[4]:
    st.subheader("Risk")
    if holdings.empty:
        st.info("No holdings.")
    else:
        by_name = holdings.groupby("Name", dropna=True)["Value (€)"].sum().sort_values(ascending=False)
        total = by_name.sum()
        top3 = by_name.head(3).sum()
        c1, c2 = st.columns(2)
        c1.metric("Top-3 concentration", f"{(top3 / total * 100):.0f}%" if total else "—")
        c2.metric("Positions", int(metrics["position_count"]))
        st.markdown("**Weights**")
        for name, val in by_name.items():
            st.markdown(f"- {name}: {(val/total*100):.1f}%" if total else f"- {name}")
    st.caption("Beta vs SPY, max drawdown and VAR need a price history feed (future wiring).")

# --- Tab 6: Scenarios -------------------------------------------------------
with tabs[5]:
    st.subheader("Scenarios")
    st.caption("What-if modeling on the live holdings (sell X, market −20%, EUR/USD move, add to a name).")
    scen = st.text_area(
        "Describe the scenario",
        height=120,
        placeholder="e.g. If I sell half my SOL and add it to GOOGL, what happens to allocation and tax?",
        key="pf_scen_text",
    )
    run_skill("Run scenario", "modules.finance.portfolio_skills", "scenario", [scen], key="pf_scen")

# --- Tab 7: Tax -------------------------------------------------------------
with tabs[6]:
    st.subheader("Tax")
    st.caption("German Abgeltungsteuer ≈ 26.375% on realized gains. Crypto held >12 months is tax-free; "
               "equities are not. Lot-level realized-gain tracking needs buy/sell history (not in the snapshot).")
    if not holdings.empty:
        st.markdown("**Current positions (for holding-period planning)**")
        st.dataframe(
            holdings[["Name", "Type", "Value (€)", "Snapshot Date"]],
            use_container_width=True, hide_index=True,
        )
    st.info("Run real-estate / income tax scenarios in the **Money** workspace → Tax tab.")
