"""Project workspace (hidden, URL-accessible) — Phase 9a.

Opened in a new browser tab from the Projects overview: ``/workspace_project?id=<NN>``.
Renders the locked single-scroll workspace (`Phase_9_Deep_Dive_Designs.md` §#3):
milestones, checkable next steps (write back to README), David-defined key files,
subfolders, drafts, Ask Claude, project-tagged tasks, decisions, and the README.
Not a place for deliverable work — that happens in Cowork.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime
from pathlib import Path

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from core import vault, markdown
from core.config import SYSTEM_PATH, get_logger
from modules.projects import workspace
from modules.agents.skills import ask_about_project
from modules.agents import background

logger = get_logger(__name__)
PROJECT_INDEX_PATH = SYSTEM_PATH / "Project_Index.md"
TASKS_PATH = SYSTEM_PATH / "Task_Command_Center.md"
DECISION_LOG_PATH = SYSTEM_PATH / "Decision_Log.md"

st.set_page_config(page_title="Command Center", layout="wide")
inject_theme()
inject_shortcuts()


# --- helpers ----------------------------------------------------------------
def status_span(label: str, color: str) -> str:
    return (
        f'<span style="color:{color}; font-size:0.85rem; font-weight:600; '
        f'letter-spacing:0.05em;">{label}</span>'
    )


def _open(path: Path) -> None:
    try:
        os.startfile(str(path))  # noqa: S606 — Windows only, intentional
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not open {path.name}: {exc}")


def _countdown(iso_date: str | None) -> str:
    if not iso_date:
        return ""
    try:
        d = date.fromisoformat(iso_date)
    except ValueError:
        return ""
    delta = (d - date.today()).days
    if delta == 0:
        return "today"
    return f"in {delta}d" if delta > 0 else f"{abs(delta)}d ago"


def _project_keywords(folder_name: str) -> list[str]:
    """Tokens used to match tasks / decisions to this project (len>=3).

    Includes the whole de-prefixed name (so short names like "K&E" still match)
    plus its individual word tokens.
    """
    base = re.sub(r"^\d+_", "", folder_name)
    toks = re.split(r"[_\s&]+", base)
    out = [base] if len(base) >= 3 else []
    out += [t for t in toks if len(t) >= 3]
    # de-dupe, preserve order
    seen, uniq = set(), []
    for t in out:
        if t.lower() not in seen:
            seen.add(t.lower())
            uniq.append(t)
    return uniq


# --- resolve the project from ?id= ------------------------------------------
projects = markdown.parse_projects(vault.read_md(PROJECT_INDEX_PATH))
ids = [p["id"] for p in projects]
by_id = {p["id"]: p for p in projects}

pid = st.query_params.get("id")
if pid not in ids:
    st.title("Project Workspace")
    if pid:
        st.warning(f"Unknown project id: {pid}")
    chosen = st.selectbox(
        "Pick a project",
        options=ids,
        format_func=lambda i: f"{i}  {by_id[i]['name'].replace('_', ' ')}",
    )
    if st.button("Open"):
        st.query_params["id"] = chosen
        st.rerun()
    st.stop()

proj = by_id[pid]
try:
    root = workspace.project_root(pid)
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()
readme_path = root / "README.md"
readme = vault.read_md(readme_path)

# --- Header -----------------------------------------------------------------
label, color = markdown.status_display(proj)
st.title(f"{pid}  {proj['name'].replace('_', ' ')}")
st.markdown(status_span(label, color), unsafe_allow_html=True)

milestones = workspace.parse_milestones(readme)
steps = workspace.parse_next_steps(readme)
open_steps = [s for s in steps if not s["checked"]]
if open_steps:
    st.markdown(f"**The one thing:** {open_steps[0]['text']}")

# --- Section 1: Milestones --------------------------------------------------
with st.container(border=True):
    st.subheader("Milestones")
    if not milestones:
        st.caption("Define a `## Milestones` section in the README.")
    else:
        timeline = len([m for m in milestones if m.get("date")]) >= 3
        for m in milestones:
            cd = _countdown(m.get("date"))
            datestr = m.get("date") or "—"
            prefix = f"`{datestr}`" + (f" · _{cd}_" if cd else "")
            st.markdown(f"- {prefix} — {m['text']}")
        if timeline:
            st.caption("Dated milestones above are in chronological order.")

# --- Section 2: Next Steps (checkable, writes back to README) ---------------
with st.container(border=True):
    st.subheader("Next Steps")
    if not steps:
        st.caption("Define a `## Next Steps` section in the README.")
    for s in steps:
        key = f"ns_{pid}_{s['line_index']}"
        # Split toggle (checkbox) from label (markdown) so that bold/italic
        # markdown in the step text renders instead of showing literally.
        col1, col2 = st.columns([1, 20])
        with col1:
            new_val = st.checkbox(
                "", value=s["checked"], key=key, label_visibility="collapsed"
            )
        with col2:
            st.markdown(s["text"])
        if new_val != s["checked"]:
            try:
                workspace.toggle_next_step(pid, s["line_index"])
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                logger.exception("toggle_next_step failed")
                st.error(f"Could not update README: {exc}")

    def _add_step() -> None:
        text = (st.session_state.get(f"addstep_{pid}") or "").strip()
        if not text:
            return
        try:
            workspace.add_next_step(pid, text)
            st.session_state[f"addstep_{pid}"] = ""
            st.session_state["_step_msg"] = ("ok", "Added next step")
        except Exception as exc:  # noqa: BLE001
            logger.exception("add_next_step failed")
            st.session_state["_step_msg"] = ("err", f"Could not add: {exc}")

    st.text_input("Quick-add a next step", key=f"addstep_{pid}")
    st.button("Add step", on_click=_add_step, key=f"addstep_btn_{pid}")
    _m = st.session_state.pop("_step_msg", None)
    if _m:
        (st.toast if _m[0] == "ok" else st.error)(_m[1])

# --- Section 3: Key Files (David-defined) -----------------------------------
with st.container(border=True):
    st.subheader("Key Files")
    st.caption("David-defined in the README — not auto-detected by recency.")
    kfs = workspace.parse_key_files(readme, root)
    if not kfs:
        st.caption("Define a `## Key Files` section in the README.")
    for i, f in enumerate(kfs):
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"**{f.name}**")
            if f.exists():
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                st.caption(f"modified {mtime:%Y-%m-%d %H:%M}")
            else:
                st.caption("file not found at the path in README")
        if c2.button("Open in OS", key=f"kf_{i}", disabled=not f.exists()):
            _open(f)

# --- Section 4: Subfolders --------------------------------------------------
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

# --- Section 5: Drafts pending send -----------------------------------------
with st.container(border=True):
    st.subheader("Drafts pending send")
    drafts = workspace.list_drafts(pid)
    if not drafts:
        st.caption("No drafts staged in this project's Drafts/ folder.")
    for i, d in enumerate(drafts):
        c1, c2 = st.columns([5, 1])
        with c1:
            badge = status_span("SENT", "#10B981") if d["is_sent"] else status_span("PENDING", "#F59E0B")
            st.markdown(f"**{d['name']}**  {badge}", unsafe_allow_html=True)
            st.caption(d["modified"].strftime("%Y-%m-%d %H:%M"))
        if c2.button("Open", key=f"draft_{i}"):
            _open(Path(d["path"]))

# --- Section 6: Ask Claude about this project -------------------------------
with st.container(border=True):
    st.subheader("Ask Claude about this project")
    st.caption("Loads this project's key files and answers via `claude -p` (zero API cost).")
    question = st.text_area("Question", key=f"ask_{pid}")
    ask_bg = st.checkbox("Run in background", key=f"ask_bg_{pid}")
    if st.button("Ask", key=f"ask_btn_{pid}", type="primary"):
        if not question.strip():
            st.warning("Type a question first.")
        elif ask_bg:
            try:
                info = background.launch(
                    module_path="modules.agents.skills.ask_about_project",
                    callable_name="ask",
                    args=[pid, question],
                    label=f"Ask {pid}",
                )
                st.toast(f"Started in background: {info['run_id']}")
            except Exception as exc:  # noqa: BLE001
                logger.exception("Background launch failed")
                st.error(f"Could not launch in background: {exc}")
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

# --- Section 7: Tasks tagged with this project ------------------------------
with st.container(border=True):
    st.subheader("Tasks for this project")
    keywords = _project_keywords(proj["folder"])
    tasks_md = vault.read_md(TASKS_PATH)
    matches: list[dict] = []
    if tasks_md and keywords:
        for i, line in enumerate(tasks_md.split("\n")):
            m = re.match(r"^\s*-\s\[([ xX])\]\s?(.*)$", line)
            if not m:
                continue
            text = m.group(2)
            if any(kw.lower() in text.lower() for kw in keywords):
                matches.append({"line_index": i, "text": text.strip(),
                                "checked": m.group(1).lower() == "x"})
    if not matches:
        st.caption(f"No tasks mention this project (keywords: {', '.join(keywords) or '—'}).")
    for t in matches:
        key = f"task_{pid}_{t['line_index']}"
        # Split toggle (checkbox) from label (markdown) so that bold/italic
        # markdown in the task text renders instead of showing literally.
        col1, col2 = st.columns([1, 20])
        with col1:
            new_val = st.checkbox(
                "", value=t["checked"], key=key, label_visibility="collapsed"
            )
        with col2:
            st.markdown(t["text"])
        if new_val != t["checked"]:
            new_md, _ = markdown.toggle_task(tasks_md, t["line_index"])
            vault.write_md(TASKS_PATH, new_md)
            st.toast("Saved")
            st.rerun()

    def _add_task() -> None:
        text = (st.session_state.get(f"addtask_{pid}") or "").strip()
        if not text:
            return
        tag = _project_keywords(proj["folder"])
        hashtag = f" #{tag[0]}" if tag else ""
        cur = vault.read_md(TASKS_PATH)
        new = (cur.rstrip("\n") + f"\n- [ ] {text}{hashtag}\n") if cur else f"- [ ] {text}{hashtag}\n"
        vault.write_md(TASKS_PATH, new)
        st.session_state[f"addtask_{pid}"] = ""
        st.session_state["_task_msg"] = "Added task"

    st.text_input("Quick-add a task (scoped to this project)", key=f"addtask_{pid}")
    st.button("Add task", on_click=_add_task, key=f"addtask_btn_{pid}")
    _tm = st.session_state.pop("_task_msg", None)
    if _tm:
        st.toast(_tm)

# --- Section 8: Decisions about this project --------------------------------
with st.container(border=True):
    st.subheader("Decisions")
    keywords = _project_keywords(proj["folder"])
    dlog = vault.read_md(DECISION_LOG_PATH)
    shown = 0
    if dlog and keywords:
        chunks = re.split(r"(?m)^##\s+", dlog)
        for chunk in chunks[1:]:
            head, _, body = chunk.partition("\n")
            blob = f"{head}\n{body}"
            if any(kw.lower() in blob.lower() for kw in keywords):
                with st.expander(head.strip() or "(decision)", expanded=False):
                    st.markdown(body.strip() or "_(empty)_")
                shown += 1
    if shown == 0:
        st.caption("No decisions reference this project yet.")

# --- Section 9: README (collapsed) ------------------------------------------
with st.expander("README (full)", expanded=False):
    if readme:
        st.markdown(readme)
    else:
        st.caption("No README.md in this project.")
