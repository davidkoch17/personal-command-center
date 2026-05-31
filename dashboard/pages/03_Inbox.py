"""Inbox — triage MD items in 0_Inbox/ (open, move, convert to task, archive, delete)."""
import os
import shutil
from datetime import datetime

import streamlit as st

from core import vault, markdown
from core.config import INBOX_PATH, VAULT_PATH, TASKS_FILE, PROJECT_INDEX_FILE
from modules.projects import workspace

st.set_page_config(page_title="Inbox", layout="wide")
st.title("Inbox")

ARCHIVE_DIR = VAULT_PATH / "9_Archive" / "Inbox_Archive"
TASK_SECTIONS = ["This weekend", "This week", "This month"]


def _open(path) -> None:
    try:
        os.startfile(str(path))  # noqa: S606 — Windows only, intentional
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not open {path.name}: {exc}")


def _append_task_to_section(section_prefix: str, title: str) -> bool:
    """Insert ``- [ ] {title}`` under the first ``## {section_prefix}...`` heading."""
    md = vault.read_md(TASKS_FILE)
    if not md:
        return False
    lines = md.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip().lower().startswith(section_prefix.lower()):
            lines.insert(i + 1, f"- [ ] {title}")
            vault.write_md(TASKS_FILE, "\n".join(lines))  # write_md makes a .bak
            return True
    return False


# Projects available as move targets.
projects = markdown.parse_projects(vault.read_md(PROJECT_INDEX_FILE))
proj_ids = [p["id"] for p in projects]
proj_label = {p["id"]: p["name"].replace("_", " ") for p in projects}

files = vault.list_files(INBOX_PATH)
st.caption(f"{len(files)} markdown item(s) in {INBOX_PATH.name}/ (top level)")

if not files:
    st.info("Inbox is empty.")
    st.stop()

for path in files:
    fkey = path.name
    when = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    with st.container(border=True):
        st.markdown(f"**{path.name}**")
        st.caption(when)
        content = vault.read_md(path)
        preview = content[:500]
        if len(content) > 500:
            preview += "…"
        st.text(preview or "(empty)")

        c = st.columns(5)

        # 1. Open in OS
        with c[0]:
            if st.button("Open in OS", key=f"open_{fkey}"):
                _open(path)

        # 2. Move to project
        with c[1]:
            with st.popover("Move to project"):
                if proj_ids:
                    psel = st.selectbox(
                        "Project",
                        proj_ids,
                        format_func=lambda i: f"{i}  {proj_label.get(i, i)}",
                        key=f"movesel_{fkey}",
                    )
                    if st.button("Move", key=f"movebtn_{fkey}"):
                        try:
                            dest_dir = workspace.project_root(psel) / "0_Inbox"
                            dest_dir.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(path), str(dest_dir / path.name))
                            st.toast(f"Moved to {psel}")
                            st.rerun()
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"Move failed: {exc}")
                else:
                    st.caption("No projects available.")

        # 3. Convert to task
        with c[2]:
            with st.popover("Convert to task"):
                ttitle = st.text_input("Task title", value=path.stem, key=f"tt_{fkey}")
                tsec = st.selectbox("Target section", TASK_SECTIONS, key=f"ts_{fkey}")
                if st.button("Create task", key=f"tcreate_{fkey}"):
                    title = (ttitle or path.stem).strip()
                    if _append_task_to_section(tsec, title):
                        try:
                            path.unlink()
                        except Exception:  # noqa: BLE001
                            pass
                        st.toast("Task created")
                        st.rerun()
                    else:
                        st.error(f"Could not find section '{tsec}' in the task file.")

        # 4. Archive
        with c[3]:
            if st.button("Archive", key=f"arch_{fkey}"):
                try:
                    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(path), str(ARCHIVE_DIR / path.name))
                    st.toast("Archived")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Archive failed: {exc}")

        # 5. Delete (two-step confirm)
        with c[4]:
            confirm_key = f"delconfirm_{fkey}"
            if st.session_state.get(confirm_key):
                if st.button("Confirm delete", key=f"delyes_{fkey}"):
                    try:
                        path.unlink()
                        st.toast("Deleted")
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Delete failed: {exc}")
                    st.session_state.pop(confirm_key, None)
                    st.rerun()
                if st.button("Cancel", key=f"delno_{fkey}"):
                    st.session_state.pop(confirm_key, None)
                    st.rerun()
            else:
                if st.button("Delete", key=f"del_{fkey}"):
                    st.session_state[confirm_key] = True
                    st.rerun()

        if st.session_state.get(f"delconfirm_{fkey}"):
            st.warning("This permanently deletes the file. Confirm above.")
