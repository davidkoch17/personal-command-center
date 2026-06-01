"""Reading — show reading list (To read / Reading now / Done) from Reading_List.md."""
import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from core import vault, markdown
from core.config import READING_LIST_PATH

st.set_page_config(page_title="Command Center", layout="wide")
inject_theme()
inject_shortcuts()
st.title("Reading")

md = vault.read_md(READING_LIST_PATH)
if not md:
    st.error(f"Could not read {READING_LIST_PATH.name}: file is empty or missing")
    st.stop()

buckets = markdown.parse_reading_list(md)

SECTIONS = [
    ("Reading now", "reading_now"),
    ("To read", "to_read"),
    ("Done", "done"),
]

for title, key in SECTIONS:
    st.subheader(title)
    items = buckets[key]
    if items:
        for item in items:
            st.markdown(f"- {item}")
    else:
        st.caption("Nothing here yet.")
    st.write("")
