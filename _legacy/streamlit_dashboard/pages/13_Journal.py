"""Journal — Decision Log viewer/writer + weekly review launcher."""
import os
import shutil
from datetime import date, datetime

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from core import vault
from core.config import SYSTEM_PATH
from modules.projects import journal, weekly_review

st.set_page_config(page_title="Command Center", layout="wide")
inject_theme()
inject_shortcuts()
st.title("Journal")

WEEKLY_REVIEW_TEMPLATE = SYSTEM_PATH / "Weekly_Review.md"
WEEKLY_REVIEWS_DIR = SYSTEM_PATH / "Weekly_Reviews"

# 1. Add a decision -----------------------------------------------------------
with st.form("add_decision", clear_on_submit=True):
    st.subheader("Add a decision")
    d = st.date_input("Date", value=date.today())
    title = st.text_input("Title")
    context = st.text_area("Context", height=80)
    decision = st.text_area("Decision", height=80)
    rationale = st.text_area("Rationale", height=80)
    tags = st.text_input("Tags (comma-separated)")
    submitted = st.form_submit_button("Add decision")

if submitted:
    if not title.strip():
        st.error("Title is required.")
    else:
        journal.append_decision(d, title.strip(), context, decision, rationale, tags)
        st.success(f"Logged decision: {title.strip()}")
        st.rerun()

# 2. Recent decisions ---------------------------------------------------------
st.subheader("Recent decisions")
decisions = journal.list_decisions()
if not decisions:
    st.info(
        f"File not found: {journal.DECISION_LOG}. "
        "Add a decision above to create it."
    )
else:
    for entry in decisions:
        with st.expander(f"{entry['date']} — {entry['title']}", expanded=False):
            st.markdown(entry["body"])

# 3. Weekly review draft ------------------------------------------------------
st.subheader("Weekly review")
if st.button("Draft this week's review"):
    st.session_state["wr_draft"] = weekly_review.draft_this_week()

if "wr_draft" in st.session_state:
    edited = st.text_area(
        "This week's review (editable)",
        value=st.session_state["wr_draft"],
        height=400,
        key="wr_draft_text",
    )
    cols = st.columns([1, 1])
    if cols[0].button("Save weekly review"):
        path = weekly_review.save_weekly_review(edited)
        st.session_state.pop("wr_draft", None)
        st.toast(f"Saved {path.name}")
        st.rerun()
    if cols[1].button("Discard draft"):
        st.session_state.pop("wr_draft", None)
        st.rerun()

# 4. Weekly Reviews -----------------------------------------------------------
with st.expander("Weekly Reviews", expanded=False):
    review_files = vault.list_files(WEEKLY_REVIEWS_DIR)
    if review_files:
        for p in review_files:
            when = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            cols = st.columns([4, 1])
            cols[0].markdown(f"- **{p.name}** — {when}")
            if cols[1].button("Open", key=f"open_review_{p.name}"):
                try:
                    os.startfile(str(p))  # noqa: S606 — Windows only, intentional
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not open {p.name}: {exc}")
    else:
        st.caption("No weekly reviews yet.")

    if st.button("Start a new weekly review"):
        new_path = WEEKLY_REVIEWS_DIR / f"{date.today().isoformat()}.md"
        if new_path.exists():
            st.warning(f"{new_path.name} already exists.")
        else:
            WEEKLY_REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
            if WEEKLY_REVIEW_TEMPLATE.exists():
                shutil.copy2(WEEKLY_REVIEW_TEMPLATE, new_path)
            else:
                new_path.write_text(
                    f"# Weekly Review — {date.today().isoformat()}\n",
                    encoding="utf-8",
                )
            st.success(f"Created {new_path.name}")
            st.rerun()
