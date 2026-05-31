"""Ideas — surface the business-idea pipeline from 1_Projects/98_Ideen/."""
import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from modules.projects import ideas
from modules.projects.ideas import IDEEN_PATH

st.set_page_config(page_title="Ideas", layout="wide")
inject_theme()
inject_shortcuts()
st.title("Ideas")
st.caption(
    "Pipeline of business ideas. Each gets validated through the "
    "Idea Validation System before activation."
)

items = ideas.list_ideas()

if not items:
    st.info(
        f"File not found: {IDEEN_PATH}. "
        "Create it in the vault to populate this view."
    )
    st.stop()

st.markdown(f"**{len(items)} ideas in pipeline**")
st.write("")

for item in items:
    with st.expander(item["name"], expanded=False):
        st.markdown(item["content"])
        st.caption(item["source_path"])
