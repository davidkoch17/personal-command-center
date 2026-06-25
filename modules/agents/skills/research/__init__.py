"""Research skills package (Phase C).

Nine background research skills, all sharing one output contract — a polished
``.docx`` deep-dive + a machine-readable ``.json`` sidecar saved under
``4_Areas/Investing/Stock_Reports/<TARGET>/``. The dashboard reads the sidecar;
it never parses Word.

Public callables (the SKILL_REGISTRY entry points) are re-exported here so the
background bootstrap can ``import_module("modules.agents.skills.research")`` and
``getattr`` the skill by name.
"""
from modules.agents.skills.research.engine import (
    generate,
    latest_for_ticker,
    list_reports,
)
from modules.agents.skills.research.skills import (
    SKILLS,
    earnings_review,
    insider_scan,
    macro_brief,
    peer_comparison,
    sector_deepdive,
    short_thesis,
    stock_analysis,
    thirteen_f_tracker,
    valuation_refresh,
)

__all__ = [
    "SKILLS",
    "generate",
    "list_reports",
    "latest_for_ticker",
    "stock_analysis",
    "earnings_review",
    "sector_deepdive",
    "peer_comparison",
    "valuation_refresh",
    "macro_brief",
    "short_thesis",
    "insider_scan",
    "thirteen_f_tracker",
]
