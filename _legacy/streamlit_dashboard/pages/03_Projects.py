"""Projects — overview grid (Phase 9a retrofit).

Read-on-click overview per the locked design (`Phase_9_Deep_Dive_Designs.md` §#3):
a "+ New project" form, a grid of project cards (status · big milestone with
countdown · current next step · last touched), and collapsible Done / Archived
sections. The per-project working view moved to the hidden `_workspace_project.py`
page, opened in a new tab via the "Open Workspace ↗" link on each card.
"""
from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from dashboard._workspace_link import workspace_link
from core import vault, markdown
from core.config import SYSTEM_PATH, get_logger
from modules.projects import workspace

logger = get_logger(__name__)
PROJECT_INDEX_PATH = SYSTEM_PATH / "Project_Index.md"

st.set_page_config(page_title="Command Center", layout="wide")
inject_theme()
inject_shortcuts()
st.title("Projects")
st.caption("Overview only. Deliverable work happens in Cowork; open a project workspace in a new tab.")


# --- helpers ----------------------------------------------------------------
def status_span(label: str, color: str) -> str:
    return (
        f'<span style="color:{color}; font-size:0.78rem; font-weight:600; '
        f'letter-spacing:0.05em;">{label}</span>'
    )


def _countdown(iso_date: str | None) -> str:
    """Human countdown for a milestone date: 'today', 'in 7d', '3d ago'."""
    if not iso_date:
        return ""
    try:
        d = date.fromisoformat(iso_date)
    except ValueError:
        return ""
    delta = (d - date.today()).days
    if delta == 0:
        return "today"
    if delta > 0:
        return f"in {delta}d"
    return f"{abs(delta)}d ago"


def _big_milestone(milestones: list[dict]) -> dict | None:
    """Pick the soonest upcoming dated milestone; else the last dated one; else first."""
    dated = [m for m in milestones if m.get("date")]
    today = date.today().isoformat()
    upcoming = sorted([m for m in dated if m["date"] >= today], key=lambda m: m["date"])
    if upcoming:
        return upcoming[0]
    if dated:
        return sorted(dated, key=lambda m: m["date"])[-1]
    return milestones[0] if milestones else None


def _readme_text(pid: str):
    try:
        root = workspace.project_root(pid)
    except FileNotFoundError:
        return None, None
    return root, vault.read_md(root / "README.md")


def _last_touched(root) -> str:
    try:
        mtime = datetime.fromtimestamp(root.stat().st_mtime)
    except OSError:
        return "—"
    secs = (datetime.now() - mtime).total_seconds()
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def _render_card(proj: dict) -> None:
    with st.container(border=True):
        display_name = proj["name"].replace("_", " ")
        st.markdown(f"**{proj['id']}  {display_name}**")
        label, color = markdown.status_display(proj)
        st.markdown(status_span(label, color), unsafe_allow_html=True)

        root, readme = _readme_text(proj["id"])
        if readme:
            milestones = workspace.parse_milestones(readme)
            steps = workspace.parse_next_steps(readme)
            big = _big_milestone(milestones)
            if big:
                cd = _countdown(big.get("date"))
                cd_txt = f"  ·  _{cd}_" if cd else ""
                st.markdown(f"{big['text']}{cd_txt}")
            else:
                st.caption("Define a milestone in README.")
            open_steps = [s for s in steps if not s["checked"]]
            if open_steps:
                st.caption(f"{open_steps[0]['text']}")
            elif steps:
                st.caption("All next steps done.")
            else:
                st.caption("Define Next Steps in README.")
            st.caption(f"Last touched {_last_touched(root)}")
        else:
            st.caption("No README — define Milestones / Next Steps / Key Files.")

        workspace_link("Open Workspace ↗", "project", proj["id"])


# --- + New project ----------------------------------------------------------
with st.expander("New project", expanded=False):
    with st.form("new_project_form", clear_on_submit=True):
        np_name = st.text_input("Project name", placeholder="e.g. Padel Accessories Brand")
        np_flow = st.radio(
            "Type", ["Flow A (business venture)", "Flow B (personal / decision)"],
            help="Flow A graduates from a validated idea; Flow B is a personal project.",
        )
        np_seed = st.text_area("README seed (Goal / context)", height=100)
        np_submit = st.form_submit_button("Create project", type="primary")
    if np_submit:
        if not np_name.strip():
            st.warning("Enter a project name.")
        else:
            try:
                flow = "Flow A" if np_flow.startswith("Flow A") else "Flow B"
                folder = workspace.create_project(np_name.strip(), flow, np_seed)
                st.success(
                    f"Created `{folder.name}`. Add it to Project_Index.md (with a RAG "
                    f"status) during your Weekly Review so it appears in the grid."
                )
            except FileExistsError:
                st.error("A project folder with that index already exists.")
            except Exception as exc:  # noqa: BLE001
                logger.exception("create_project failed")
                st.error(f"Could not create project: {exc}")


# --- project grid -----------------------------------------------------------
projects = markdown.parse_projects(vault.read_md(PROJECT_INDEX_PATH))
if not projects:
    st.info("No projects found in Project_Index.md.")
    st.stop()


def _bucket(proj: dict) -> str:
    label, _ = markdown.status_display(proj)
    text = (proj.get("status_text") or "").lower()
    if "archiv" in text:
        return "archived"
    if label == "DONE":
        return "done"
    return "active"


active = [p for p in projects if _bucket(p) == "active"]
done = [p for p in projects if _bucket(p) == "done"]
archived = [p for p in projects if _bucket(p) == "archived"]

st.write("")
if active:
    cols = st.columns(4)
    for i, proj in enumerate(active):
        with cols[i % 4]:
            _render_card(proj)
else:
    st.caption("No active projects.")

# --- Done / Archived --------------------------------------------------------
st.write("")
with st.expander(f"Done ({len(done)})", expanded=False):
    if not done:
        st.caption("No completed projects.")
    else:
        cols = st.columns(4)
        for i, proj in enumerate(done):
            with cols[i % 4]:
                _render_card(proj)

with st.expander(f"Archived ({len(archived)})", expanded=False):
    if not archived:
        st.caption("No archived projects.")
    else:
        cols = st.columns(4)
        for i, proj in enumerate(archived):
            with cols[i % 4]:
                _render_card(proj)
