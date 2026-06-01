"""Ideas — Idea Validation System workspace.

New-idea intake, active-idea cards, a 12-stage validation workspace, and the
killed-idea archive. Long runs (full validation, individual stages) are launched
detached via :mod:`modules.agents.background` so the dashboard stays interactive.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from core.config import get_logger
from modules.agents.skills import idea_validator as iv
from modules.agents import background

logger = get_logger(__name__)

st.set_page_config(page_title="Ideas", page_icon="💡", layout="wide")
inject_theme()
inject_shortcuts()

RUNNER_MODULE = "modules.agents.skills.idea_validator.runner"
BINARY_OUTPUTS = {
    "05": "05_Financial_Model.xlsx",
    "06": "06_Business_Plan.docx",
    "07": "07_Pitch_Deck.pptx",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _open_in_os(path: Path) -> None:
    try:
        os.startfile(str(path))  # noqa: S606 — Windows only, intentional
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not open {path.name}: {exc}")


def _stage_status(state: dict, stage_key: str) -> str:
    s = state.get(stage_key)
    if not s:
        return "pending"
    if s.get("stale"):
        return "stale"
    return "done"


_STATUS_ICON = {"done": "✓", "stale": "⚠", "pending": "☐", "running": "⟳"}


def _active_bg_run_for(idea_name: str) -> dict | None:
    """Return the most recent still-running background run whose run_id references
    this idea, or None. Run ids embed the label (e.g. ``..._Validate_<Idea>``)."""
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in idea_name)
    for run in background.list_recent_runs(30):
        rid = run.get("run_id", "")
        if safe in rid and run.get("status") == "running":
            return run
    return None


def _launch_full_validation(idea_name: str) -> None:
    info = background.launch(
        module_path=RUNNER_MODULE,
        callable_name="run_all",
        args=[idea_name],
        label=f"Validate {idea_name}",
    )
    st.toast(f"Full validation started in background: {info['run_id']}", icon="🚀")


def _launch_stage_bg(idea_name: str, stage_key: str) -> None:
    info = background.launch(
        module_path=RUNNER_MODULE,
        callable_name="run_stage",
        args=[idea_name, stage_key],
        label=f"Stage {stage_key} {idea_name}",
    )
    st.toast(f"Stage {stage_key} started in background: {info['run_id']}", icon="🚀")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("💡 Ideas")
st.caption(
    "Idea Validation System — drop an idea, run a 12-stage validation pack "
    "(market, competition, financials, plan, deck, risk, scorecard, pre-mortem), "
    "then make a real go / park / kill call. Inference via `claude -p` — zero API cost."
)

active_idea = st.session_state.get("active_idea")


# ---------------------------------------------------------------------------
# New idea intake
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("New idea")
    with st.form("new_idea_form", clear_on_submit=True):
        new_name = st.text_input("Idea name", placeholder="e.g. Carbon Accounting for SMBs")
        new_brief = st.text_area(
            "Idea brief",
            height=200,
            placeholder=(
                "Problem, solution, target customer, value prop, why now, why you, "
                "biggest unknowns, kill criteria you'd accept. Be specific — vague "
                "briefs produce vague analysis. (~500-2000 chars)"
            ),
        )
        submitted = st.form_submit_button("Create idea", type="primary")
    if submitted:
        if not new_name.strip() or not new_brief.strip():
            st.warning("Enter both an idea name and a brief.")
        else:
            try:
                folder = iv.create_idea(new_name.strip(), new_brief.strip())
                st.session_state["active_idea"] = folder.name
                st.toast(f"Created idea folder: {folder.name}", icon="✅")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                logger.exception("create_idea failed")
                st.error(f"Could not create idea: {exc}")


# ---------------------------------------------------------------------------
# Workspace view (an idea is selected)
# ---------------------------------------------------------------------------
def _render_workspace(idea_name: str) -> None:
    folder = iv.idea_folder(idea_name)
    if not folder.exists():
        st.warning(f"Idea folder not found: {idea_name}")
        st.session_state.pop("active_idea", None)
        return

    state = iv._read_state(folder)

    top_l, top_r = st.columns([4, 1])
    with top_l:
        st.header(idea_name.replace("_", " "))
    with top_r:
        if st.button("← Back to all ideas", key="back_to_list"):
            st.session_state.pop("active_idea", None)
            st.rerun()

    # Active background-run banner
    run = _active_bg_run_for(idea_name)
    if run:
        started = run.get("started_at", "?")
        st.info(
            f"⟳ A validation run is in progress in the background "
            f"(started {started}). Refresh this page to update progress."
        )

    # MASTER.md preview
    master = folder / "MASTER.md"
    if master.exists():
        with st.expander("MASTER.md", expanded=True):
            st.markdown(master.read_text(encoding="utf-8"))

    # Progress strip
    done = sum(1 for k, _, _ in iv.STAGES if _stage_status(state, k) == "done")
    st.markdown(f"**Progress — {done} / {len(iv.STAGES)} stages complete**")
    st.progress(done / len(iv.STAGES))
    strip = "  ".join(
        f"{_STATUS_ICON[_stage_status(state, k)]} {k}" for k, _, _ in iv.STAGES
    )
    st.caption(strip)
    st.caption("✓ done · ⚠ stale (re-run recommended) · ☐ pending")

    st.write("")
    st.markdown("### Stages")

    for stage_key, slug, filename in iv.STAGES:
        status = _stage_status(state, stage_key)
        title = f"{_STATUS_ICON[status]} Stage {stage_key} — {slug.replace('_', ' ').title()}"
        with st.expander(title, expanded=False):
            out_path = folder / filename

            # Latest output
            if out_path.exists():
                st.caption(
                    f"{filename} · modified "
                    f"{datetime.fromtimestamp(out_path.stat().st_mtime):%Y-%m-%d %H:%M}"
                )
                try:
                    st.markdown(out_path.read_text(encoding="utf-8"))
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not read output: {exc}")
            else:
                st.caption("Not generated yet.")

            # Binary deliverable (xlsx / docx / pptx)
            bin_name = BINARY_OUTPUTS.get(stage_key)
            if bin_name:
                bin_path = folder / bin_name
                if bin_path.exists():
                    bc1, bc2 = st.columns(2)
                    with bc1:
                        st.download_button(
                            f"⬇ Download {bin_name}",
                            data=bin_path.read_bytes(),
                            file_name=bin_name,
                            key=f"dl_{stage_key}",
                        )
                    with bc2:
                        if st.button(f"Open {bin_name} in OS", key=f"open_{stage_key}"):
                            _open_in_os(bin_path)
                else:
                    st.caption(f"({bin_name} not generated yet.)")

            # Run controls
            run_in_bg = st.checkbox(
                "Run in background", key=f"bg_{stage_key}", value=False
            )
            label = "Re-run" if out_path.exists() else "Run now"
            if st.button(label, key=f"run_{stage_key}", type="primary"):
                if run_in_bg:
                    _launch_stage_bg(idea_name, stage_key)
                    st.rerun()
                else:
                    with st.spinner(
                        f"Running Stage {stage_key} via claude -p — this can take "
                        f"several minutes…"
                    ):
                        try:
                            iv.run_stage(idea_name, stage_key)
                            st.toast(f"Stage {stage_key} complete", icon="✅")
                            st.rerun()
                        except Exception as exc:  # noqa: BLE001
                            logger.exception("run_stage failed")
                            st.error(f"Stage {stage_key} failed: {exc}")

    # Run full validation (always background — 30-60 min)
    st.write("")
    with st.container(border=True):
        st.markdown("**Run full validation (all 12 stages)**")
        st.caption(
            "Runs Stages 2-12 sequentially in the background (~30-60 min). "
            "Refresh this page to track progress; outputs appear stage by stage."
        )
        if st.button("🚀 Run full validation", key="run_all", type="primary"):
            _launch_full_validation(idea_name)
            st.rerun()

    # Mark as decided
    st.write("")
    with st.container(border=True):
        st.markdown("**Mark as decided**")
        decision = st.radio(
            "Decision", ["Pursue", "Park", "Kill"], horizontal=True, key="decision_radio"
        )
        reason = st.text_area("Reason / notes", key="decision_reason", height=80)
        if st.button("Apply decision", key="apply_decision"):
            if decision == "Kill":
                if not reason.strip():
                    st.warning("Add a kill reason so the pattern analysis is useful.")
                else:
                    try:
                        iv.kill_idea(idea_name, reason.strip())
                        st.session_state.pop("active_idea", None)
                        st.toast(f"Killed: {idea_name}", icon="🗑️")
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("kill_idea failed")
                        st.error(f"Could not kill idea: {exc}")
            else:
                # Pursue / Park — annotate MASTER.md via Python file I/O.
                try:
                    note = (
                        f"\n\n## Decision\n{decision} — "
                        f"{datetime.now():%Y-%m-%d %H:%M}\n\n{reason.strip()}\n"
                    )
                    mp = folder / "MASTER.md"
                    existing = mp.read_text(encoding="utf-8") if mp.exists() else ""
                    mp.write_text(existing + note, encoding="utf-8")
                    st.toast(f"Marked as {decision}", icon="✅")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("decision annotate failed")
                    st.error(f"Could not record decision: {exc}")


# ---------------------------------------------------------------------------
# List view (no idea selected)
# ---------------------------------------------------------------------------
def _render_list() -> None:
    ideas = iv.list_ideas()
    if not ideas:
        st.info("No ideas yet. Use **New idea** above to start one.")
    else:
        st.markdown(f"### Active ideas ({len(ideas)})")
        for item in ideas:
            name = item["name"]
            n_done = item["stages_complete"]
            with st.container(border=True):
                c_name, c_prog, c_btn = st.columns([3, 2, 1])
                with c_name:
                    st.markdown(f"**{name.replace('_', ' ')}**")
                    run = _active_bg_run_for(name)
                    if run:
                        st.caption("⟳ validation running in background")
                with c_prog:
                    st.progress(
                        min(n_done, len(iv.STAGES)) / len(iv.STAGES),
                        text=f"{n_done} / {len(iv.STAGES)} stages",
                    )
                with c_btn:
                    if st.button("Open", key=f"open_idea_{name}"):
                        st.session_state["active_idea"] = name
                        st.rerun()

                qa1, qa2 = st.columns([3, 1])
                with qa1:
                    action = st.selectbox(
                        "Quick action",
                        ["—", "Run full validation"]
                        + [f"Re-run stage {k}" for k, _, _ in iv.STAGES],
                        key=f"qa_{name}",
                        label_visibility="collapsed",
                    )
                with qa2:
                    if st.button("Go", key=f"qa_go_{name}"):
                        if action == "Run full validation":
                            _launch_full_validation(name)
                            st.rerun()
                        elif action.startswith("Re-run stage "):
                            sk = action.replace("Re-run stage ", "").strip()
                            _launch_stage_bg(name, sk)
                            st.rerun()

    # Killed ideas archive
    st.write("")
    killed = iv.list_killed()
    with st.expander(f"Killed ideas ({len(killed)})", expanded=False):
        if not killed:
            st.caption("No killed ideas yet.")
        else:
            # Pattern view — naive count of recurring kill-reason keywords.
            patterns: dict[str, int] = {}
            keywords = [
                "market", "competit", "capital", "time", "moat",
                "interest", "regulat", "team", "margin",
            ]
            for k in killed:
                low = k["reason"].lower()
                for kw in keywords:
                    if kw in low:
                        patterns[kw] = patterns.get(kw, 0) + 1
            if patterns:
                summary = "; ".join(
                    f"{kw}: {n}" for kw, n in sorted(
                        patterns.items(), key=lambda x: -x[1]
                    )
                )
                st.caption(f"Kill-reason patterns — {summary}")
            for k in killed:
                st.markdown(f"**{k['name'].replace('_', ' ')}**")
                st.caption(k["reason"] or "(no reason recorded)")


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
if active_idea:
    _render_workspace(active_idea)
else:
    _render_list()
