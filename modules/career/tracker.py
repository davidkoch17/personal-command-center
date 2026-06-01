"""Career checklists: onboarding admin + technicals refresh tracker (Phase 9b).

Both are simple Markdown checkbox files in ``3_Career/05_Current_Job/``. Toggles
write back via Python file I/O (the vault writer keeps a ``.bak``). Files are
created from defaults on first save.
"""
from __future__ import annotations

from core import vault
from core.config import CAREER_PATH

ONBOARDING_FILE = CAREER_PATH / "05_Current_Job" / "Onboarding.md"
TECHNICALS_FILE = CAREER_PATH / "05_Current_Job" / "Technicals_Tracker.md"

DEFAULT_ONBOARDING = [
    "FFM address registered (Anmeldung)",
    "GKV / health insurance elected",
    "BU (Berufsunfähigkeit) policy in place",
    "Employment contract signed & filed",
    "Equipment / IT setup confirmed",
    "Bank details submitted to payroll",
]

TECHNICALS_MODULES = [
    "DCF",
    "LBO",
    "M&A accretion / dilution",
    "Trading comps",
    "Precedent transactions",
    "Sector primers",
]


def parse_checklist(md: str) -> list[dict]:
    """Parse ``- [ ]`` / ``- [x]`` lines into ``[{text, checked}]``."""
    items = []
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("- [ ] "):
            items.append({"text": s[6:].strip(), "checked": False})
        elif s.lower().startswith("- [x] "):
            items.append({"text": s[6:].strip(), "checked": True})
    return items


def build_checklist_md(title: str, items: list[dict]) -> str:
    lines = [f"# {title}", ""]
    for it in items:
        box = "x" if it["checked"] else " "
        lines.append(f"- [{box}] {it['text']}")
    return "\n".join(lines) + "\n"


def _read_or_default(path, title: str, defaults: list[str]) -> list[dict]:
    md = vault.read_md(path)
    if md:
        items = parse_checklist(md)
        if items:
            return items
    return [{"text": t, "checked": False} for t in defaults]


def read_onboarding() -> list[dict]:
    return _read_or_default(ONBOARDING_FILE, "Onboarding admin", DEFAULT_ONBOARDING)


def save_onboarding(items: list[dict]) -> None:
    vault.write_md(ONBOARDING_FILE, build_checklist_md("Onboarding admin", items))


def read_technicals() -> list[dict]:
    return _read_or_default(TECHNICALS_FILE, "Technicals refresh tracker", TECHNICALS_MODULES)


def save_technicals(items: list[dict]) -> None:
    vault.write_md(TECHNICALS_FILE, build_checklist_md("Technicals refresh tracker", items))
