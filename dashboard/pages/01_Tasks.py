"""Tasks — full task list from Task_Command_Center.md with toggleable checkboxes."""
import streamlit as st

from core import vault, markdown
from core.config import SYSTEM_PATH

TASKS_PATH = SYSTEM_PATH / "Task_Command_Center.md"

st.set_page_config(page_title="Tasks", layout="wide")
st.title("Tasks")
st.caption(f"Source: {TASKS_PATH.name} — toggles write back to the vault (a .bak is kept).")

md = vault.read_md(TASKS_PATH)
if not md:
    st.error(f"Could not read {TASKS_PATH.name}: file is empty or missing")
    st.stop()

# Collect level-2 section headings in document order.
section_headers = [line[3:].strip() for line in md.split("\n") if line.startswith("## ")]

rendered = 0
for header in section_headers:
    bullets = markdown.parse_section_bullets(md, header)
    if not bullets:
        continue  # skip prose / non-task sections
    expanded = rendered < 2  # first 2 task sections open by default
    with st.expander(header, expanded=expanded):
        for item in bullets:
            key = f"task_{item['line_index']}"
            new_val = st.checkbox(item["text"], value=item["checked"], key=key)
            if new_val != item["checked"]:
                new_md, _ = markdown.toggle_task(md, item["line_index"])
                vault.write_md(TASKS_PATH, new_md)
                st.toast("Saved")
                st.rerun()
    rendered += 1

if rendered == 0:
    st.info("No task sections with checkboxes found.")
