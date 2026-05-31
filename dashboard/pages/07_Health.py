"""Health Journal — add daily entries, view recent ones, Whoop placeholder."""
from datetime import date

import streamlit as st

from core import vault
from modules.habits import health_journal

st.set_page_config(page_title="Health", layout="wide")
st.title("Health Journal")

# ----------------------------------------------------------------------------
# Add today's entry
# ----------------------------------------------------------------------------
st.subheader("Add today's entry")

with st.form("health_entry", clear_on_submit=False):
    entry_date = st.date_input("Date", value=date.today())
    col_a, col_b = st.columns(2)
    with col_a:
        mood = st.slider("Mood", 1, 10, 5)
        sleep_h = st.number_input("Sleep hours", min_value=0.0, max_value=24.0, value=7.0, step=0.5)
    with col_b:
        energy = st.slider("Energy", 1, 10, 5)
        supplements = st.text_input("Supplements taken today", placeholder="e.g. creatine, omega-3, vitamin D")
    workout = st.text_input("Workout", placeholder="type of workout, duration, notes")
    diet = st.text_area("Diet notes", height=80)
    notes = st.text_area("General notes", height=120)
    submitted = st.form_submit_button("Save entry")

if submitted:
    try:
        path = health_journal.save_entry(
            entry_date, mood, energy, sleep_h, workout, diet, supplements, notes
        )
        st.toast("Saved.")
        st.success(f"Saved {path.name}")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not save entry: {exc}")

# ----------------------------------------------------------------------------
# Recent entries
# ----------------------------------------------------------------------------
st.subheader("Recent entries")
recent = health_journal.list_recent(14)
if not recent:
    st.info("No journal entries yet.")
else:
    for path in recent:
        with st.expander(path.stem):
            st.markdown(vault.read_md(path))

# ----------------------------------------------------------------------------
# Whoop placeholder
# ----------------------------------------------------------------------------
st.divider()
st.subheader("Whoop")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Recovery", "— %")
col2.metric("Sleep", "— h")
col3.metric("HRV", "— ms")
col4.metric("Day Strain", "—")
st.caption("_Whoop API integration pending._")
