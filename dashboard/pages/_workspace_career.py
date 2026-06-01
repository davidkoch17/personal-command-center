"""Career workspace (hidden, new-tab) — Phase 9b.

URL: ``/workspace_career``. Single-scroll 10-section deep dive: countdown,
onboarding admin (write-back), technicals tracker (write-back) + per-module quiz,
3-statement model status, first-90-days plan, deal pipeline (info-barrier
limited), mentor/network, long-term strategy, documents, and Ask Claude.
"""
from __future__ import annotations

import os
from datetime import date

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from dashboard._skillrun import run_skill
from core import vault
from core import config
from core.config import (
    CAREER_PATH, CAREER_STRATEGY_PATH, EVERCORE_START_DATE, PERSONAL_MEMORY_FILE,
)
from modules.career import tracker
from modules.agents.claude_cli import run_claude

CAREER = "modules.agents.skills.career"

st.set_page_config(page_title="Career Workspace", layout="wide")
inject_theme()
inject_shortcuts()

EVERCORE_START = date.fromisoformat(EVERCORE_START_DATE)
CURRENT_JOB = CAREER_PATH / "05_Current_Job"
MODEL_FILE = CURRENT_JOB / "3_Statement_Model.xlsx"
PLAN_FILE = CURRENT_JOB / "First_90_Days.md"
MENTOR_FILE = CURRENT_JOB / "Mentor_Network.md"
PIPELINE_FILE = CURRENT_JOB / "Deal_Pipeline.md"

st.title("Career Workspace")


def _editable(path, title: str, height: int = 160) -> None:
    current = vault.read_md(path)
    edited = st.text_area(title, value=current, height=height, key=f"edit_{path.name}",
                          label_visibility="collapsed")
    if st.button(f"Save {title}", key=f"save_{path.name}"):
        vault.write_md(path, edited)
        st.toast(f"Saved {title}", icon="✅")


# --- Section 1: Countdown + critical dates ----------------------------------
with st.container(border=True):
    st.subheader("1 · Countdown + critical dates")
    days = (EVERCORE_START - date.today()).days
    st.markdown(f"**{days} days** until Evercore start ({EVERCORE_START_DATE}).")
    if config.info_barrier_active():
        st.warning("🔒 Info-barrier active — deal specifics are limited to sector/title below.")

# --- Section 2: Onboarding admin (write-back) -------------------------------
with st.container(border=True):
    st.subheader("2 · Onboarding admin")
    onboarding = tracker.read_onboarding()
    changed = False
    for i, it in enumerate(onboarding):
        val = st.checkbox(it["text"], value=it["checked"], key=f"onb_{i}")
        if val != it["checked"]:
            onboarding[i]["checked"] = val
            changed = True
    if changed:
        tracker.save_onboarding(onboarding)
        st.rerun()

# --- Section 3: Technicals refresh tracker (write-back) + quiz --------------
with st.container(border=True):
    st.subheader("3 · Technicals refresh tracker")
    technicals = tracker.read_technicals()
    changed = False
    for i, it in enumerate(technicals):
        val = st.checkbox(it["text"], value=it["checked"], key=f"tech_{i}")
        if val != it["checked"]:
            technicals[i]["checked"] = val
            changed = True
    if changed:
        tracker.save_technicals(technicals)
        st.rerun()
    st.markdown("**Quiz me on a module**")
    module = st.selectbox("Module", [it["text"] for it in technicals], key="quiz_module")
    run_skill("Quiz me", CAREER, "quiz_technicals", [module], key="career_quiz")

# --- Section 4: 3-statement model status ------------------------------------
with st.container(border=True):
    st.subheader("4 · 3-statement model")
    if MODEL_FILE.exists():
        st.caption(f"Model file present: {MODEL_FILE.name}")
        if st.button("Open model in OS", key="open_model"):
            try:
                os.startfile(str(MODEL_FILE))  # noqa: S606
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not open: {exc}")
    else:
        st.caption(f"No model yet — save one as {MODEL_FILE.name} in 05_Current_Job/.")
    st.markdown("**Model checker** — paste key outputs / formulas / structure to review:")
    model_summary = st.text_area("Model description", height=120, key="model_summary",
                                 label_visibility="collapsed")
    run_skill("Check model", CAREER, "model_checker", [model_summary], key="career_modelcheck")

# --- Section 5: First 90 days plan (editable) -------------------------------
with st.container(border=True):
    st.subheader("5 · First 90 days plan")
    _editable(PLAN_FILE, "First 90 days", height=180)

# --- Section 6: Deal pipeline (info-barrier limited) ------------------------
with st.container(border=True):
    st.subheader("6 · Deal pipeline")
    if config.info_barrier_active():
        st.error("🔒 Info-barrier active — record sector/title only. No deal specifics.")
    else:
        st.caption("Pre-Evercore: use this to practice deal notes. Post-start, sector/title only.")
    _editable(PIPELINE_FILE, "Deal pipeline notes", height=140)
    st.markdown("**Deal note practice** — paste an article to structure into a deal note:")
    article = st.text_area("Article", height=140, key="deal_article", label_visibility="collapsed")
    run_skill("Make deal note", CAREER, "deal_note", [article], key="career_dealnote")

# --- Section 7: Mentor / network plan (editable) ----------------------------
with st.container(border=True):
    st.subheader("7 · Mentor / network plan")
    _editable(MENTOR_FILE, "Mentor / network", height=140)

# --- Section 8: Career strategy long-term -----------------------------------
with st.container(border=True):
    st.subheader("8 · Career strategy (long-term)")
    strat_files = vault.list_files(CAREER_STRATEGY_PATH)
    if strat_files:
        st.markdown(vault.read_md(strat_files[0]))
    else:
        st.caption(f"No strategy files in {CAREER_STRATEGY_PATH}.")

# --- Section 9: Documents / files -------------------------------------------
with st.container(border=True):
    st.subheader("9 · Documents / files")
    if CURRENT_JOB.exists():
        docs = sorted([p for p in CURRENT_JOB.iterdir() if p.is_file()])
        for i, p in enumerate(docs):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"**{p.name}**")
            if c2.button("Open", key=f"career_doc_{i}"):
                try:
                    os.startfile(str(p))  # noqa: S606
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not open: {exc}")
    else:
        st.caption("05_Current_Job/ not found.")

# --- Prep skills ------------------------------------------------------------
with st.container(border=True):
    st.subheader("Prep skills")
    s1, s2 = st.columns(2)
    with s1:
        st.markdown("**Mock interview**")
        kind = st.radio("Type", ["behavioral", "technical"], horizontal=True, key="mock_kind")
        run_skill("Run mock interview", CAREER, "mock_interview", [kind], key="career_mock")
    with s2:
        st.markdown("**Industry primer**")
        sector = st.text_input("Sector", key="primer_sector", placeholder="e.g. semiconductors")
        run_skill("Generate primer", CAREER, "industry_primer", [sector], key="career_primer")
    st.markdown("**Career letter draft**")
    lk1, lk2 = st.columns([1, 2])
    letter_kind = lk1.selectbox("Kind", ["cover letter", "LinkedIn outreach", "thank-you note"],
                                key="letter_kind")
    letter_ctx = lk2.text_input("Context / recipient", key="letter_ctx")
    run_skill("Draft letter", CAREER, "career_letter_draft", [letter_kind, letter_ctx], key="career_letter")

# --- Section 10: Ask Claude about my career ---------------------------------
with st.container(border=True):
    st.subheader("10 · Ask Claude about my career")
    q = st.text_area("Question", key="career_ask_q", height=80)
    if st.button("Ask", key="career_ask_btn", type="primary"):
        if not q.strip():
            st.warning("Type a question first.")
        else:
            memory = vault.read_md(PERSONAL_MEMORY_FILE)
            prompt = (
                f"You are advising David on his career. Context (Personal_Memory):\n\n{memory}\n\n"
                f"---\n\nQuestion: {q.strip()}\n"
            )
            with st.spinner("Asking Claude…"):
                try:
                    st.session_state["career_ask_resp"] = run_claude(prompt, timeout=300)
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Ask failed: {exc}")
    resp = st.session_state.get("career_ask_resp")
    if resp:
        st.markdown(resp)
