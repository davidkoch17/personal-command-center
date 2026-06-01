"""Ideas — overview grid (Phase 9a retrofit of the Idea Validation System).

Read-on-click overview: a "+ New idea" intake (quick capture / full intake), a
grid of active-idea cards (status · validation progress · recommendation · score
· last touched), and the killed-idea archive with naive pattern analysis. The
12-stage validation workspace moved to the hidden `_workspace_idea.py` page,
opened in a new tab via each card's "Open Workspace ↗" link.
"""
from __future__ import annotations

import re
from datetime import datetime

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from dashboard._workspace_link import workspace_link
from core.config import get_logger
from modules.agents.skills import idea_validator as iv

logger = get_logger(__name__)

st.set_page_config(page_title="Command Center", layout="wide")
inject_theme()
inject_shortcuts()

N_STAGES = len(iv.STAGES)


# --- helpers ----------------------------------------------------------------
def _master_text(folder) -> str:
    p = folder / "MASTER.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _recommendation(folder) -> str | None:
    """Pull a recommendation from MASTER.md / scorecard, if any."""
    for name in ("MASTER.md", "11_Decision_Scorecard.md"):
        p = folder / name
        if not p.exists():
            continue
        m = re.search(r"(?:Final recommendation|Recommendation):\s*\n?(.+)",
                      p.read_text(encoding="utf-8"))
        if m and m.group(1).strip() and "(set after" not in m.group(1):
            return m.group(1).strip()
    return None


def _score(folder) -> str | None:
    """Pull an aggregate score from the scorecard, if present (e.g. '72/100')."""
    p = folder / "11_Decision_Scorecard.md"
    if not p.exists():
        return None
    m = re.search(r"(?:Aggregate|Total|Overall)\s*[Ss]core[^0-9]*([0-9]+(?:\.[0-9]+)?\s*/\s*[0-9]+)",
                  p.read_text(encoding="utf-8"))
    return m.group(1).replace(" ", "") if m else None


def _status(folder, n_done: int) -> tuple[str, str]:
    master = _master_text(folder).lower()
    if "## decision" in master or "decision:" in master:
        return "DECIDED", "#3B82F6"
    if n_done == 0:
        return "NEW", "#9CA3AF"
    return "VALIDATING", "#F59E0B"


def _last_touched(folder) -> str:
    try:
        mtime = datetime.fromtimestamp(folder.stat().st_mtime)
    except OSError:
        return "—"
    secs = (datetime.now() - mtime).total_seconds()
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def status_span(label: str, color: str) -> str:
    return (
        f'<span style="color:{color}; font-size:0.78rem; font-weight:600; '
        f'letter-spacing:0.05em;">{label}</span>'
    )


# --- Header -----------------------------------------------------------------
st.title("Ideas")
st.caption(
    "Idea Validation System — capture an idea, run a 12-stage validation pack, "
    "then make a real go / park / kill call. Open a workspace in a new tab to run it."
)


# --- + New idea -------------------------------------------------------------
with st.container(border=True):
    st.subheader("New idea")
    tab_quick, tab_full = st.tabs(["Quick capture", "Full intake"])

    with tab_quick:
        with st.form("quick_idea_form", clear_on_submit=True):
            q_name = st.text_input("Idea name", key="q_name")
            q_brief = st.text_area("One-liner (refine later in the workspace)", height=90, key="q_brief")
            q_submit = st.form_submit_button("Capture idea", type="primary")
        if q_submit:
            if not q_name.strip() or not q_brief.strip():
                st.warning("Enter an idea name and at least a one-liner.")
            else:
                try:
                    folder = iv.create_idea(q_name.strip(), q_brief.strip())
                    st.toast(f"Created idea: {folder.name}")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("create_idea (quick) failed")
                    st.error(f"Could not create idea: {exc}")

    with tab_full:
        with st.form("full_idea_form", clear_on_submit=True):
            f_name = st.text_input("Idea name", key="f_name")
            f_brief = st.text_area(
                "Idea brief",
                height=200,
                placeholder=(
                    "Problem, solution, target customer, value prop, why now, why you, "
                    "biggest unknowns, kill criteria you'd accept. Be specific — vague "
                    "briefs produce vague analysis. (~500-2000 chars)"
                ),
                key="f_brief",
            )
            f_submit = st.form_submit_button("Create idea", type="primary")
        if f_submit:
            if not f_name.strip() or not f_brief.strip():
                st.warning("Enter both an idea name and a brief.")
            else:
                try:
                    folder = iv.create_idea(f_name.strip(), f_brief.strip())
                    st.toast(f"Created idea folder: {folder.name}")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("create_idea (full) failed")
                    st.error(f"Could not create idea: {exc}")


# --- Active idea cards ------------------------------------------------------
ideas = iv.list_ideas()
st.write("")
if not ideas:
    st.info("No ideas yet. Use **New idea** above to start one.")
else:
    st.markdown(f"### Active ideas ({len(ideas)})")
    cols = st.columns(3)
    for i, item in enumerate(ideas):
        folder = item["path"]
        n_done = min(item["stages_complete"], N_STAGES)
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{item['name'].replace('_', ' ')}**")
                label, color = _status(folder, n_done)
                st.markdown(status_span(label, color), unsafe_allow_html=True)
                st.progress(n_done / N_STAGES, text=f"{n_done} / {N_STAGES} stages")
                rec = _recommendation(folder)
                if rec:
                    st.caption(f"{rec[:80]}")
                sc = _score(folder)
                if sc:
                    st.caption(f"Score: {sc}")
                st.caption(f"Last touched {_last_touched(folder)}")
                workspace_link("Open Workspace ↗", "idea", item["name"])


# --- Killed ideas archive ---------------------------------------------------
st.write("")
killed = iv.list_killed()
with st.expander(f"Killed ideas ({len(killed)})", expanded=False):
    if not killed:
        st.caption("No killed ideas yet.")
    else:
        patterns: dict[str, int] = {}
        keywords = ["market", "competit", "capital", "time", "moat",
                    "interest", "regulat", "team", "margin"]
        for k in killed:
            low = k["reason"].lower()
            for kw in keywords:
                if kw in low:
                    patterns[kw] = patterns.get(kw, 0) + 1
        if patterns:
            summary = "; ".join(
                f"{kw}: {n}" for kw, n in sorted(patterns.items(), key=lambda x: -x[1])
            )
            st.caption(f"Kill-reason patterns — {summary}")
        for k in killed:
            st.markdown(f"**{k['name'].replace('_', ' ')}**")
            st.caption(k["reason"] or "(no reason recorded)")
