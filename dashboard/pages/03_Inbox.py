"""Inbox — show MD items in 0_Inbox/ (non-recursive)."""
import os
from datetime import datetime

import streamlit as st

from core import vault
from core.config import INBOX_PATH

st.set_page_config(page_title="Inbox", layout="wide")
st.title("Inbox")

files = vault.list_files(INBOX_PATH)
st.caption(f"{len(files)} markdown item(s) in {INBOX_PATH.name}/ (top level)")

if not files:
    st.info("Inbox is empty.")
    st.stop()

for path in files:
    when = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    with st.container(border=True):
        st.markdown(f"**{path.name}**")
        st.caption(when)
        content = vault.read_md(path)
        preview = content[:500]
        if len(content) > 500:
            preview += "…"
        st.text(preview or "(empty)")
        if st.button("Open in OS", key=f"open_{path.name}"):
            try:
                os.startfile(str(path))  # noqa: S606 — Windows only, intentional
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not open {path.name}: {exc}")
