"""Search across the vault."""
import os

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from modules.search.index import search

st.set_page_config(page_title="Command Center", layout="wide")
inject_theme()
inject_shortcuts()
st.title("Search")

query = st.text_input("Search the vault", placeholder="Type to search across all markdown notes...")

if query:
    results = search(query, limit=30)
    st.caption(f"{len(results)} matches")
    for r in results:
        with st.container(border=True):
            st.markdown(
                f"**{r['relative']}**  · {r['match_count']} matches · "
                f"modified {r['mtime'].strftime('%Y-%m-%d')}"
            )
            st.markdown(
                f"<span style='color:#9CA3AF'>{r['snippet']}…</span>",
                unsafe_allow_html=True,
            )
            if st.button("Open", key=f"open_{r['relative']}"):
                try:
                    os.startfile(str(r["path"]))  # noqa: S606 — Windows only, intentional
                except Exception as e:  # noqa: BLE001
                    st.error(f"Could not open: {e}")
else:
    st.info("Type a query above to search across your vault.")
