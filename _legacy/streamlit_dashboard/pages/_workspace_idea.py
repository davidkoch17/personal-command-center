"""Idea validation workspace (hidden, URL-accessible) — Phase 9a.

Opened in a new browser tab from the Ideas overview: ``/workspace_idea?id=<name>``.
Renders the 12-stage validation workspace (Phase 8 content under the Phase 9
deep-dive pattern): progress strip, run controls (full / per-stage, with a
background option for the long runs), per-stage outputs with .xlsx/.docx/.pptx
"Open in OS" buttons, the idea brief, editable overrides, a decision panel, and
an inline "Ask Claude about this idea".
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from core import vault
from core.config import get_logger
from modules.agents.skills import idea_validator as iv
from modules.agents import background
from modules.agents.claude_cli import run_claude

logger = get_logger(__name__)

st.set_page_config(page_title="Command Center", layout="wide")
inject_theme()
inject_shortcuts()

RUNNER_MODULE = "modules.agents.skills.idea_validator.runner"
BINARY_OUTPUTS = {
    "05": "05_Financial_Model.xlsx",
    "06": "06_Business_Plan.docx",
    "07": "07_Pitch_Deck.pptx",
}
_STATUS_ICON = {"done": "[x]", "stale": "[!]", "pending": "[ ]", "running": "[~]"}


# --- helpers ----------------------------------------------------------------
def _open_in_os(path: Path) -> None:
    try:
        os.startfile(str(path))  # noqa: S606 — Windows only, intentional
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not open {path.name}: {exc}")


def _stage_status(state: dict, stage_key: str) -> str:
    s = state.get(stage_key)
    if not s:
        return "pending"
    return "stale" if s.get("stale") else "done"


def _active_bg_run_for(idea_name: str) -> dict | None:
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in idea_name)
    for run in background.list_recent_runs(30):
        rid = run.get("run_id", "")
        if safe in rid and run.get("status") == "running":
            return run
    return None


def _launch_full_validation(idea_name: str) -> None:
    info = background.launch(
        module_path=RUNNER_MODULE, callable_name="run_all",
        args=[idea_name], label=f"Validate {idea_name}",
    )
    st.toast(f"Full validation started: {info['run_id']} — track it on the "
             "Background Runs page.")


def _launch_stage_bg(idea_name: str, stage_key: str) -> None:
    info = background.launch(
        module_path=RUNNER_MODULE, callable_name="run_stage",
        args=[idea_name, stage_key], label=f"Stage {stage_key} {idea_name}",
    )
    st.toast(f"Stage {stage_key} started: {info['run_id']} — track it on the "
             "Background Runs page.")


# --- resolve idea from ?id= -------------------------------------------------
ideas = iv.list_ideas()
names = [i["name"] for i in ideas]
idea_name = st.query_params.get("id")

if not idea_name or iv.idea_folder(idea_name).resolve() not in {i["path"].resolve() for i in ideas}:
    st.title("Idea Workspace")
    if idea_name:
        st.warning(f"Unknown idea: {idea_name}")
    if not names:
        st.info("No ideas yet. Create one on the Ideas page.")
        st.stop()
    chosen = st.selectbox("Pick an idea", names, format_func=lambda n: n.replace("_", " "))
    if st.button("Open"):
        st.query_params["id"] = chosen
        st.rerun()
    st.stop()

folder = iv.idea_folder(idea_name)
state = iv._read_state(folder)
done = sum(1 for k, _, _ in iv.STAGES if _stage_status(state, k) == "done")

# --- Header -----------------------------------------------------------------
st.title(idea_name.replace('_', ' '))

master = folder / "MASTER.md"
if master.exists():
    with st.expander("MASTER.md", expanded=True):
        st.markdown(master.read_text(encoding="utf-8"))

run = _active_bg_run_for(idea_name)
if run:
    st.info(
        f"A validation run is in progress in the background "
        f"(started {run.get('started_at', '?')}). Refresh to update progress."
    )

# --- Section 1: Progress strip ----------------------------------------------
with st.container(border=True):
    st.subheader("Progress")
    st.markdown(f"**{done} / {len(iv.STAGES)} stages complete**")
    st.progress(done / len(iv.STAGES))
    strip = "  ".join(f"{_STATUS_ICON[_stage_status(state, k)]} {k}" for k, _, _ in iv.STAGES)
    st.caption(strip)
    st.caption("[x] done · [!] stale (re-run recommended) · [ ] pending")

# --- Section 2: Run controls ------------------------------------------------
with st.container(border=True):
    st.subheader("Run validation")
    st.caption("Full run does Stages 2-12 sequentially in the background (~30-60 min).")
    if st.button("Run full validation", key="run_all", type="primary"):
        _launch_full_validation(idea_name)
        st.rerun()

# --- Section 3: Per-stage outputs -------------------------------------------
with st.container(border=True):
    st.subheader("Stages")
    for stage_key, slug, filename in iv.STAGES:
        status = _stage_status(state, stage_key)
        title = f"{_STATUS_ICON[status]} Stage {stage_key} — {slug.replace('_', ' ').title()}"
        with st.expander(title, expanded=False):
            out_path = folder / filename
            if out_path.exists():
                st.caption(
                    f"{filename} · modified {datetime.fromtimestamp(out_path.stat().st_mtime):%Y-%m-%d %H:%M}"
                )
                try:
                    st.markdown(out_path.read_text(encoding="utf-8"))
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not read output: {exc}")
            else:
                st.caption("Not generated yet.")

            bin_name = BINARY_OUTPUTS.get(stage_key)
            if bin_name:
                bin_path = folder / bin_name
                if bin_path.exists():
                    bc1, bc2 = st.columns(2)
                    with bc1:
                        st.download_button(
                            f"Download {bin_name}", data=bin_path.read_bytes(),
                            file_name=bin_name, key=f"dl_{stage_key}",
                        )
                    with bc2:
                        if st.button(f"Open {bin_name} in OS", key=f"open_{stage_key}"):
                            _open_in_os(bin_path)
                else:
                    st.caption(f"({bin_name} not generated yet.)")

            # Phase 10a: stage runs always go background (each stage is a long
            # claude -p call). No synchronous mode.
            label = "Re-run" if out_path.exists() else "Run now"
            if st.button(label, key=f"run_{stage_key}", type="primary"):
                _launch_stage_bg(idea_name, stage_key)
                st.rerun()

# --- Section 4: Idea Brief --------------------------------------------------
with st.container(border=True):
    st.subheader("Idea Brief")
    brief = folder / "01_Idea_Brief.md"
    st.markdown(brief.read_text(encoding="utf-8") if brief.exists() else "_No brief found._")

# --- Section 5: Overrides (editable) ----------------------------------------
with st.container(border=True):
    st.subheader("Overrides")
    st.caption("David's manual corrections / assumptions. Every stage prompt reads and respects these.")
    ovr = folder / "_overrides.md"
    current = ovr.read_text(encoding="utf-8") if ovr.exists() else ""
    edited = st.text_area("Overrides", value=current, height=200, key="overrides_edit",
                          label_visibility="collapsed")
    if st.button("Save overrides", key="save_overrides"):
        try:
            vault.write_md(ovr, edited)
            st.toast("Overrides saved")
        except Exception as exc:  # noqa: BLE001
            logger.exception("save overrides failed")
            st.error(f"Could not save overrides: {exc}")

# --- Section 6: Decision panel ----------------------------------------------
with st.container(border=True):
    st.subheader("Decision")
    decision = st.radio("Decision", ["Pursue", "Park", "Kill"], horizontal=True, key="decision_radio")
    reason = st.text_area("Reason / notes", key="decision_reason", height=80)
    if st.button("Apply decision", key="apply_decision"):
        if decision == "Kill":
            if not reason.strip():
                st.warning("Add a kill reason so the pattern analysis is useful.")
            else:
                try:
                    iv.kill_idea(idea_name, reason.strip())
                    st.toast(f"Killed: {idea_name}")
                    st.success("Idea moved to the killed archive. Close this tab.")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("kill_idea failed")
                    st.error(f"Could not kill idea: {exc}")
        else:
            try:
                note = (
                    f"\n\n## Decision\n{decision} — {datetime.now():%Y-%m-%d %H:%M}\n\n{reason.strip()}\n"
                )
                existing = master.read_text(encoding="utf-8") if master.exists() else ""
                vault.write_md(master, existing + note)
                st.toast(f"Marked as {decision}")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                logger.exception("decision annotate failed")
                st.error(f"Could not record decision: {exc}")

# --- Ask Claude about this idea ---------------------------------------------
with st.container(border=True):
    st.subheader("Ask Claude about this idea")
    st.caption("Answers with the idea brief, overrides, and MASTER.md as context (zero API cost).")
    q = st.text_area("Question", key="ask_idea_q")
    if st.button("Ask", key="ask_idea_btn", type="primary"):
        if not q.strip():
            st.warning("Type a question first.")
        else:
            ctx_parts = []
            for fname in ("01_Idea_Brief.md", "_overrides.md", "MASTER.md"):
                p = folder / fname
                if p.exists():
                    ctx_parts.append(f"## {fname}\n\n{p.read_text(encoding='utf-8')}")
            context = "\n\n---\n\n".join(ctx_parts)
            prompt = (
                f"You are advising David on a business idea. Use the context below.\n\n"
                f"{context}\n\n---\n\nQuestion: {q.strip()}\n"
            )
            with st.spinner("Asking Claude…"):
                try:
                    st.session_state["ask_idea_resp"] = run_claude(prompt, timeout=300)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("ask about idea failed")
                    st.error(f"Ask failed: {exc}")
    resp = st.session_state.get("ask_idea_resp")
    if resp:
        st.markdown(resp)
