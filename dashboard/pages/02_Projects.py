"""Projects — per-project workspace: drafts, key files, subfolders, logs, templates."""
import json
import os
import re
from datetime import datetime
from pathlib import Path

import streamlit as st

from core import vault, markdown
from core.config import SYSTEM_PATH, DATA_DIR, get_logger
from modules.projects import workspace, templates
from modules.agents.skills import ask_about_project

logger = get_logger(__name__)

PROJECT_INDEX_PATH = SYSTEM_PATH / "Project_Index.md"
LAST_ACTIVE_FILE = DATA_DIR / "last_active.json"

st.set_page_config(page_title="Projects", layout="wide")
st.title("Projects")


# --- small helpers -----------------------------------------------------------
def status_span(label: str, color: str) -> str:
    """Return an HTML span rendering a colored status label."""
    return (
        f'<span style="color:{color}; font-size:0.78rem; font-weight:600; '
        f'letter-spacing:0.05em;">{label}</span>'
    )


def _ago(dt: datetime) -> str:
    """Human relative time, e.g. 'just now', '12m ago', '3h ago', '2d ago'."""
    secs = (datetime.now() - dt).total_seconds()
    if secs < 0:
        return "just now"
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def _human_size(path: Path) -> str:
    n = float(path.stat().st_size)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.0f} TB"


def _open(path: Path) -> None:
    try:
        os.startfile(str(path))  # noqa: S606 — Windows only, intentional
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not open {path.name}: {exc}")


def _last_log_entries(text: str, n: int = 5) -> list[tuple[str, str]]:
    """Return the last N ``## `` entries from a Project_Log as (header, body), newest first."""
    chunks = re.split(r"(?m)^## ", text)
    entries: list[tuple[str, str]] = []
    for chunk in chunks[1:]:
        head, _, body = chunk.partition("\n")
        entries.append((head.strip(), body.strip()))
    return entries[::-1][:n]


# --- project selection -------------------------------------------------------
projects = markdown.parse_projects(vault.read_md(PROJECT_INDEX_PATH))
if not projects:
    st.info("No projects found in Project_Index.md.")
    st.stop()

ids = [p["id"] for p in projects]
id_to_name = {p["id"]: p["name"].replace("_", " ") for p in projects}

# Selection priority: query param > session_state > last_active.json > first.
default_id = None
qp = st.query_params.get("project_id")
for candidate in (qp, st.session_state.get("active_project_id")):
    if candidate in ids:
        default_id = candidate
        break
if default_id is None and LAST_ACTIVE_FILE.exists():
    try:
        rec = json.loads(LAST_ACTIVE_FILE.read_text(encoding="utf-8"))
        if rec.get("project_id") in ids:
            default_id = rec["project_id"]
    except Exception:  # noqa: BLE001
        pass
if default_id is None:
    default_id = ids[0]

pid = st.selectbox(
    "Project",
    options=ids,
    index=ids.index(default_id),
    format_func=lambda i: f"{i}  {id_to_name.get(i, i)}",
    key="project_selectbox",
)
st.session_state["active_project_id"] = pid

# Persist last-active for Home's "Continue where you left off".
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LAST_ACTIVE_FILE.write_text(
        json.dumps(
            {
                "project_id": pid,
                "name": id_to_name.get(pid, pid),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
        ),
        encoding="utf-8",
    )
except Exception:  # noqa: BLE001
    pass

try:
    root = workspace.project_root(pid)
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

st.markdown(f"### {pid}  {id_to_name.get(pid, pid)}")

# --- 1. Current draft --------------------------------------------------------
with st.container(border=True):
    st.subheader("Current draft")
    draft = workspace.most_recent_draft(pid)
    if draft:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"**{draft.name}**")
            mtime = datetime.fromtimestamp(draft.stat().st_mtime)
            st.caption(f"modified {_ago(mtime)}  ·  {_human_size(draft)}")
        with c2:
            if st.button("Open in OS", key="open_draft"):
                _open(draft)
    else:
        st.info("No draft files found in this project yet.")

# --- 2. Recent key files -----------------------------------------------------
with st.container(border=True):
    st.subheader("Recent key files")
    kfs = workspace.key_files(pid, limit=5)
    if kfs:
        for i, f in enumerate(kfs):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f.name)
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                st.caption(f"modified {_ago(mtime)}")
            if c2.button("Open", key=f"openkf_{i}"):
                _open(f)
    else:
        st.caption("No key files yet.")

# --- 3. Subfolders -----------------------------------------------------------
with st.container(border=True):
    st.subheader("Subfolders")
    subs = workspace.list_subfolders(pid)
    if subs:
        cols = st.columns(4)
        for i, d in enumerate(subs):
            if cols[i % 4].button(d.name, key=f"sub_{i}", use_container_width=True):
                _open(d)
    else:
        st.caption("No subfolders.")

# --- 4. Session log ----------------------------------------------------------
with st.container(border=True):
    st.subheader("Session log")

    def _append_log() -> None:
        note = (st.session_state.get(f"log_{pid}") or "").strip()
        if not note:
            st.session_state["_log_msg"] = ("warn", "Note is empty.")
            return
        try:
            workspace.append_project_log(pid, note)
            st.session_state[f"log_{pid}"] = ""
            st.session_state["_log_msg"] = ("ok", "Appended to Project_Log")
        except Exception as exc:  # noqa: BLE001
            st.session_state["_log_msg"] = ("err", f"Could not append: {exc}")

    st.text_area("Quick note for this session", key=f"log_{pid}", height=100)
    st.button("Append to Project_Log", on_click=_append_log, key=f"appendlog_{pid}")
    _msg = st.session_state.pop("_log_msg", None)
    if _msg:
        kind, text = _msg
        if kind == "ok":
            st.toast(text)
        elif kind == "warn":
            st.warning(text)
        else:
            st.error(text)

    log_path = root / "Project_Log.md"
    log_text = vault.read_md(log_path)
    if log_text:
        st.caption("Recent log entries")
        for head, body in _last_log_entries(log_text, 5):
            with st.expander(head or "(entry)", expanded=False):
                st.markdown(body or "_(empty)_")
    else:
        st.caption("No Project_Log.md yet.")

# --- 5. Drafts ---------------------------------------------------------------
with st.container(border=True):
    st.subheader("Drafts")
    if st.button("New draft", key="new_draft"):
        drafts_dir = root / "Drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        new_path = drafts_dir / f"{ts}_untitled.md"
        new_path.write_text(
            "---\nstatus: pending\n---\n\n# Untitled draft\n\n", encoding="utf-8"
        )
        _open(new_path)
        st.rerun()

    drafts = workspace.list_drafts(pid)
    if drafts:
        for i, d in enumerate(drafts):
            c1, c2 = st.columns([5, 1])
            with c1:
                if d["is_sent"]:
                    badge = status_span("SENT", "#10B981")
                else:
                    badge = status_span("PENDING", "#F59E0B")
                st.markdown(f"**{d['name']}**  {badge}", unsafe_allow_html=True)
                st.caption(d["modified"].strftime("%Y-%m-%d %H:%M"))
            if c2.button("Open", key=f"opendraft_{i}"):
                _open(Path(d["path"]))
    else:
        st.caption("No drafts staged.")

# --- 6. New document from template -------------------------------------------
with st.container(border=True):
    st.subheader("New document from template")
    tmpls = templates.list_templates()
    if tmpls:
        tnames = [t.stem for t in tmpls]
        sel = st.selectbox("Template", tnames, key="tmpl_sel")
        doc_name = st.text_input("Document name", key="tmpl_name")
        if st.button("Create", key="tmpl_create"):
            if doc_name.strip():
                try:
                    dest = templates.instantiate_template(sel, pid, doc_name.strip())
                    st.toast(f"Created {dest.name}")
                    _open(dest)
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not create document: {exc}")
            else:
                st.warning("Enter a document name.")
    else:
        st.caption("No templates available in 99_System/Templates/.")

# --- 7. README ---------------------------------------------------------------
with st.expander("README", expanded=False):
    readme = root / "README.md"
    content = vault.read_md(readme)
    if content:
        st.markdown(content)
    else:
        st.caption("No README.md in this project.")

# --- 8. Ask Claude about this project ----------------------------------------
with st.container(border=True):
    st.subheader("🤖 Ask Claude about this project")
    st.caption(
        "Loads this project's key files and answers via `claude -p` "
        "(Claude Max subscription — zero API cost)."
    )
    question = st.text_area("Question", key=f"ask_{pid}")
    if st.button("Ask", key=f"ask_btn_{pid}", type="primary"):
        if not question.strip():
            st.warning("Type a question first.")
        else:
            with st.spinner("Asking Claude about this project…"):
                try:
                    st.session_state[f"ask_resp_{pid}"] = ask_about_project.ask(pid, question)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Ask-about-project failed")
                    st.error(f"Ask failed: {exc}")

    _response = st.session_state.get(f"ask_resp_{pid}")
    if _response:
        st.markdown(_response)
        if st.button("Append to Project_Log.md", key=f"ask_save_{pid}"):
            try:
                workspace.append_project_log(
                    pid, f"**Ask Claude — Q:** {question.strip()}\n\n{_response}"
                )
                st.success("Appended to Project_Log.md")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Save failed: {exc}")
