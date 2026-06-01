"""Money workspace (hidden, new-tab) — Phase 9b.

URL: ``/workspace_money``. Tab order is LOCKED: Cash Flow · Categories · Net Worth
· Forecast · Budget · Tax · Transactions. The Tax tab's Section B is the
tax-scenario workshop (free-text + structured fields → `tax_scenario_skill` →
saved to a chosen project folder).
"""
from __future__ import annotations

import json
import os

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from dashboard._skillrun import run_skill
from core import vault, markdown
from core.config import (
    DATA_DIR, FINANCE_TRACKER_FILE, PROJECT_INDEX_FILE, get_logger,
)
from modules.finance import loader, money, money_skills

logger = get_logger(__name__)
st.set_page_config(page_title="Money Workspace", layout="wide")
inject_theme()
inject_shortcuts()

PLOTLY_TEMPLATE = "plotly_dark"
EMERALD = ["#10B981", "#047857", "#34D399", "#065F46", "#6EE7B7", "#059669"]
BUDGET_FILE = DATA_DIR / "money_budget.json"


def euro(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        return f"€{float(v):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _load_budget() -> dict:
    if BUDGET_FILE.exists():
        try:
            return json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_budget(d: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BUDGET_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


st.title("Money Workspace")

tabs = st.tabs([
    "Cash Flow", "Categories", "Net Worth", "Forecast", "Budget", "Tax", "Transactions",
])

# --- Tab 1: Cash Flow -------------------------------------------------------
with tabs[0]:
    st.subheader("Income vs Expenses — 12 months")
    totals = money.monthly_totals()
    if totals.empty or not {"income", "expenses"}.issubset(totals.columns):
        st.info("Fill Income_vs_Expenses in the Excel.")
    else:
        recent = totals.sort_values("month").tail(12)
        long = recent.melt(id_vars="month", value_vars=[c for c in ["income", "expenses"] if c in recent.columns],
                           var_name="Type", value_name="Amount (€)")
        long["Type"] = long["Type"].map({"income": "Income", "expenses": "Expenses"})
        fig = px.bar(long, x="month", y="Amount (€)", color="Type", barmode="group",
                     template=PLOTLY_TEMPLATE, color_discrete_sequence=EMERALD)
        if "savings" in recent.columns and "income" in recent.columns:
            rate = (recent["savings"] / recent["income"].replace(0, pd.NA) * 100)
            fig.add_scatter(x=recent["month"], y=rate, mode="lines+markers",
                            name="Savings rate %", yaxis="y2", line=dict(color="#FBBF24"))
            fig.update_layout(yaxis2=dict(overlaying="y", side="right", title="Savings rate %"))
        fig.update_layout(height=360, margin=dict(t=10, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Account-level activity (by card)")
    tx = money.transactions_normalized()
    if not tx.empty and {"Month", "Card", "Amount (€)"}.issubset(tx.columns):
        piv = tx.pivot_table(index="Month", columns="Card", values="Amount (€)", aggfunc="sum").fillna(0)
        st.dataframe(piv.tail(6), use_container_width=True)
    else:
        st.caption("No card-level data available.")

# --- Tab 2: Categories ------------------------------------------------------
with tabs[1]:
    st.subheader("Category drill-down")
    pivot = money.monthly_spending_by_category()
    if pivot.empty:
        st.info("Add categorized transactions in the Excel.")
    else:
        cats = list(pivot.columns)
        cat = st.selectbox("Category", cats, key="money_cat")
        series = pivot[cat]
        fig = px.line(series.reset_index(), x="Month", y=cat, markers=True,
                      template=PLOTLY_TEMPLATE, color_discrete_sequence=EMERALD)
        fig.update_layout(height=300, margin=dict(t=10, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)
        last = series.iloc[-1]
        avg3 = series.tail(4).iloc[:-1].mean() if len(series) >= 2 else last
        c1, c2 = st.columns(2)
        c1.metric("Last month", euro(last))
        c2.metric("vs prior 3-mo avg", euro(avg3),
                  delta=f"{((last-avg3)/avg3*100):.0f}%" if avg3 else None)
        if avg3 and last > 1.3 * avg3:
            st.warning(f"⚠ {cat} is {((last-avg3)/avg3*100):.0f}% above its 3-month average.")

# --- Tab 3: Net Worth -------------------------------------------------------
with tabs[2]:
    st.subheader("Net worth over time")
    nw = loader.net_worth()
    if nw.empty or "Total Net Worth (€)" not in nw.columns:
        st.info("Fill the Net_Worth sheet in the Excel.")
    else:
        comp_cols = [c for c in ["Bank Balance (€)", "Trade Republic (€)", "Crypto (€)"] if c in nw.columns]
        if comp_cols and "Month" in nw.columns:
            long = nw.melt(id_vars="Month", value_vars=comp_cols, var_name="Bucket", value_name="€")
            fig = px.area(long, x="Month", y="€", color="Bucket",
                          template=PLOTLY_TEMPLATE, color_discrete_sequence=EMERALD)
            fig.update_layout(height=320, margin=dict(t=10, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)
        nw_vals = nw["Total Net Worth (€)"].dropna()
        if len(nw_vals) >= 2:
            chg = nw_vals.iloc[-1] - nw_vals.iloc[-2]
            st.metric("Latest net worth", euro(nw_vals.iloc[-1]), delta=euro(chg))

# --- Tab 4: Forecast --------------------------------------------------------
with tabs[3]:
    st.subheader("Cash-flow forecast")
    st.caption("Projects 6/12 months from current burn + known income (Evercore from 01.07) and expenses.")
    scen = st.text_area("Scenario / assumptions (optional)", height=100, key="money_forecast_scen",
                        placeholder="e.g. Evercore base €X, FFM rent €Y, cut subscriptions €Z/mo")
    run_skill("Run forecast", "modules.finance.money_skills", "forecast_cash_flow",
              [scen], key="money_forecast")

# --- Tab 5: Budget ----------------------------------------------------------
with tabs[4]:
    st.subheader("Budget — target vs actual")
    pivot = money.monthly_spending_by_category()
    budget = _load_budget()
    if pivot.empty:
        st.info("Add categorized transactions to set budgets.")
    else:
        last = pivot.iloc[-1]
        with st.form("budget_form"):
            st.caption("Set a monthly € target per category. Saved to the repo (data/money_budget.json).")
            new_budget = {}
            for cat in pivot.columns:
                new_budget[str(cat)] = st.number_input(
                    str(cat), min_value=0.0, value=float(budget.get(str(cat), 0.0)), step=50.0,
                    key=f"budget_{cat}",
                )
            if st.form_submit_button("Save budget"):
                _save_budget(new_budget)
                st.toast("Budget saved", icon="✅")
                budget = new_budget
        rows = []
        for cat in pivot.columns:
            tgt = float(budget.get(str(cat), 0.0))
            act = float(last.get(cat, 0.0))
            rows.append({"Category": str(cat), "Target (€)": tgt, "Actual (€)": act,
                         "Variance (€)": act - tgt})
        bdf = pd.DataFrame(rows)
        st.dataframe(bdf, use_container_width=True, hide_index=True)
        over = bdf[(bdf["Target (€)"] > 0) & (bdf["Actual (€)"] > bdf["Target (€)"])]
        for _, r in over.iterrows():
            st.warning(f"⚠ {r['Category']}: {euro(r['Actual (€)'])} vs target {euro(r['Target (€)'])}")

# --- Tab 6: Tax -------------------------------------------------------------
with tabs[5]:
    st.subheader("Tax")

    # Section A — current state (passive)
    with st.container(border=True):
        st.markdown("**Section A — Current state**")
        st.caption("YTD income & deductible-expense summaries are best generated via the skills below "
                   "(they read the live ledger). Evercore Lohnsteuer applies from 01.07.2026.")
        c1, c2 = st.columns(2)
        with c1:
            run_skill("Tax-deductible review", "modules.finance.money_skills",
                      "tax_deductible_review", [], key="money_deduct")
        with c2:
            run_skill("Find expense optimizations", "modules.finance.money_skills",
                      "find_expense_optimizations", [], key="money_optim")

    # Section B — run a tax scenario (the killer feature)
    with st.container(border=True):
        st.markdown("**Section B — Run a tax scenario**")
        free = st.text_area(
            "Describe your hypothetical (talk to it like a CFO)",
            height=120,
            placeholder="e.g. Buy €450k flat in FFM, 20% down, €30k repairs, intent to rent — 10-year tax impact?",
            key="tax_free",
        )
        with st.expander("Optional structured fields"):
            f1, f2, f3 = st.columns(3)
            purchase = f1.number_input("Purchase price (€)", min_value=0.0, step=10000.0, key="tax_purchase")
            repairs = f2.number_input("Repair costs (€)", min_value=0.0, step=1000.0, key="tax_repairs")
            rental = f3.number_input("Annual rental income (€)", min_value=0.0, step=1000.0, key="tax_rental")
            horizon = st.number_input("Time horizon (years)", min_value=0, step=1, value=10, key="tax_horizon")

        # Save target dropdown — active projects with Scenarios/ + generic Steuern default
        projects = markdown.parse_projects(vault.read_md(PROJECT_INDEX_FILE))
        save_options = {"Generic — 2_Personal/03_Steuern/Scenarios": ""}
        for p in projects:
            label = f"{p['folder']} — Scenarios"
            save_options[label] = f"1_Projects/{p['folder']}/Scenarios"
        save_label = st.selectbox("Save analysis to", list(save_options.keys()), key="tax_save_to")

        # Build the full scenario description from free text + structured fields.
        structured = []
        if purchase:
            structured.append(f"purchase price €{purchase:,.0f}")
        if repairs:
            structured.append(f"repair costs €{repairs:,.0f}")
        if rental:
            structured.append(f"annual rental income €{rental:,.0f}")
        if horizon:
            structured.append(f"time horizon {int(horizon)} years")
        full_desc = free + (("\n\nStructured inputs: " + "; ".join(structured)) if structured else "")
        save_to = save_options[save_label]

        bg = st.checkbox("Run in background", key="tax_bg")
        if st.button("Run tax scenario", key="tax_run", type="primary"):
            if not free.strip():
                st.warning("Describe the hypothetical first.")
            elif bg:
                from modules.agents import background
                try:
                    info = background.launch(
                        module_path="modules.finance.money_skills", callable_name="tax_scenario",
                        args=[full_desc, save_to], label="Tax scenario",
                    )
                    st.toast(f"Started in background: {info['run_id']}", icon="🚀")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not launch: {exc}")
            else:
                with st.spinner("Running tax scenario via claude -p (web search) — can take minutes…"):
                    try:
                        out_path = money_skills.tax_scenario(full_desc, save_to or None)
                        st.session_state["tax_result_path"] = str(out_path)
                        st.toast(f"Saved to {out_path}", icon="✅")
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("tax_scenario failed")
                        st.error(f"Tax scenario failed: {exc}")
        rp = st.session_state.get("tax_result_path")
        if rp:
            from pathlib import Path
            p = Path(rp)
            st.caption(f"Saved: {rp}")
            if p.exists():
                st.markdown(p.read_text(encoding="utf-8"))
                if st.button("Open in OS", key="tax_open"):
                    try:
                        os.startfile(rp)  # noqa: S606
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Could not open: {exc}")

    # Section C — year-end checklist (passive reminders)
    with st.container(border=True):
        st.markdown("**Section C — Year-end checklist**")
        for item in [
            "Gather Lohnsteuerbescheinigung (Evercore, from 01.07)",
            "Collect deductible receipts (Werbungskosten, work equipment)",
            "PKV / BU premium statements for Sonderausgaben",
            "Capital gains statements (Trade Republic, Kraken)",
            "Submit Steuererklärung before the deadline",
        ]:
            st.markdown(f"- [ ] {item}")

    st.divider()
    run_skill("Quarterly money review", "modules.finance.money_skills",
              "quarterly_money_review", [], key="money_qreview")
    run_skill("Bill forecaster (next month)", "modules.finance.money_skills",
              "bill_forecaster", [], key="money_bills")

# --- Tab 7: Transactions ----------------------------------------------------
with tabs[6]:
    st.subheader("Transactions ledger")
    if st.button("Open in Excel", key="money_open_excel"):
        try:
            os.startfile(str(FINANCE_TRACKER_FILE))  # noqa: S606
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not open Excel: {exc}")
    tx = money.transactions_normalized()
    if tx.empty:
        st.info("No transactions in the Excel.")
    else:
        cols = [c for c in ["Date", "Description", "Amount (€)", "Category", "Card"] if c in tx.columns]
        f1, f2 = st.columns(2)
        cat_filter = f1.multiselect("Category", sorted(tx["Category"].dropna().unique()) if "Category" in tx else [])
        search = f2.text_input("Search description")
        view = tx.sort_values("Date", ascending=False)
        if cat_filter:
            view = view[view["Category"].isin(cat_filter)]
        if search:
            view = view[view["Description"].astype(str).str.contains(search, case=False, na=False)]
        st.dataframe(view[cols], use_container_width=True, hide_index=True)
