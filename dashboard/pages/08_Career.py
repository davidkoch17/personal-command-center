"""Career — Evercore countdown + prep checklist + reference sections from 3_Career/."""
from datetime import date, datetime
from pathlib import Path

import streamlit as st

from dashboard._theme import inject_theme, inject_shortcuts
from core import vault
from core.config import VAULT_PATH

st.set_page_config(page_title="Career", layout="wide")
inject_theme()
inject_shortcuts()
st.title("Career")

CAREER_PATH = VAULT_PATH / "3_Career"
PREP_CHECKLIST_PATH = CAREER_PATH / "05_Current_Job" / "Prep_Checklist.md"
EVERCORE_START = date(2026, 7, 1)

DEFAULT_PREP_ITEMS = [
    "Build 3-statement model (target name TBD)",
    "Refresh technicals (DCF, LBO, M&A accretion/dilution)",
    "Onboarding admin (FFM address change)",
    "Read recent Evercore deals (last 12 months)",
    "Set up first-90-days plan",
]


def parse_checklist(md: str) -> list[dict]:
    """Parse `- [ ]` / `- [x]` lines into [{text, checked}]."""
    items = []
    for line in md.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ] "):
            items.append({"text": stripped[6:].strip(), "checked": False})
        elif stripped.lower().startswith("- [x] "):
            items.append({"text": stripped[6:].strip(), "checked": True})
    return items


def build_checklist_md(items: list[dict]) -> str:
    """Render checklist items back to markdown."""
    lines = ["# Evercore Prep Checklist", ""]
    for it in items:
        box = "x" if it["checked"] else " "
        lines.append(f"- [{box}] {it['text']}")
    return "\n".join(lines) + "\n"


def list_with_mtime(directory: Path) -> list[tuple[str, str]]:
    """Return [(name, 'YYYY-MM-DD HH:MM')] for entries in a directory."""
    if not directory.exists():
        return []
    out = []
    for p in sorted(directory.iterdir()):
        when = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        out.append((p.name, when))
    return out


# 1. Top row — Evercore countdown ---------------------------------------------
days_remaining = (EVERCORE_START - date.today()).days
c1, c2, c3 = st.columns(3)
c1.metric("Days to Evercore start", days_remaining)
c2.metric("BU status", "Not yet applied")
c3.metric("GKV status", "To elect at onboarding")

# 2. Prep checklist -----------------------------------------------------------
with st.container(border=True):
    st.subheader("Evercore Prep")
    existing_md = vault.read_md(PREP_CHECKLIST_PATH)
    if existing_md:
        items = parse_checklist(existing_md)
    else:
        items = [{"text": t, "checked": False} for t in DEFAULT_PREP_ITEMS]

    new_states = []
    for i, it in enumerate(items):
        new_states.append(
            st.checkbox(it["text"], value=it["checked"], key=f"prep_{i}")
        )

    updated = [
        {"text": it["text"], "checked": new_states[i]}
        for i, it in enumerate(items)
    ]
    # Persist only when the user actually toggled something. Comparing against the
    # rebuilt baseline (not raw file text) means simply viewing the page never
    # writes — the file is created on first save, per spec.
    baseline_md = build_checklist_md(items)
    new_md = build_checklist_md(updated)
    if new_md != baseline_md:
        vault.write_md(PREP_CHECKLIST_PATH, new_md)

# 3. Reference sections -------------------------------------------------------
with st.expander("WHU Studium status", expanded=False):
    whu_dir = CAREER_PATH / "02_WHU_Studium"
    content = vault.read_md(whu_dir / "README.md")
    if not content:
        md_files = vault.list_files(whu_dir)
        if md_files:
            content = vault.read_md(md_files[0])
    if content:
        st.markdown(content)
    else:
        st.info(
            f"File not found: {whu_dir}. "
            "Create it in the vault to populate this view."
        )

with st.expander("Zeugnisse", expanded=False):
    entries = list_with_mtime(CAREER_PATH / "03_Zeugnisse")
    if entries:
        for name, when in entries:
            st.markdown(f"- **{name}** — {when}")
    else:
        st.info(
            f"File not found: {CAREER_PATH / '03_Zeugnisse'}. "
            "Create it in the vault to populate this view."
        )

with st.expander("CV / Applications", expanded=False):
    cv_dir = CAREER_PATH / "04_CV_Applications"
    if cv_dir.exists():
        entries = [
            (p.name, datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"))
            for p in sorted(cv_dir.iterdir())
            if "archive" not in p.name.lower()
        ]
        if entries:
            for name, when in entries:
                st.markdown(f"- **{name}** — {when}")
        else:
            st.caption("Nothing here yet (archive folders excluded).")
    else:
        st.info(
            f"File not found: {cv_dir}. "
            "Create it in the vault to populate this view."
        )
