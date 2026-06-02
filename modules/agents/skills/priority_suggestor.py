"""Priority Suggestor — when multiple deadlines cluster, recommend an order.

Reads the hard dates from ``Task_Command_Center.md`` plus the active-project
context from ``Project_Index.md``, then asks Claude (via the local ``claude -p``
CLI) to reorder the upcoming deadlines into a recommended sequence. Returns a
JSON-safe dict so the API can hand it straight to the frontend.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

from core import vault, markdown
from core.config import TASKS_FILE, PROJECT_INDEX_FILE, get_logger
from modules.agents.claude_cli import run_claude

logger = get_logger(__name__)

_EMPTY = {"recommendation": "", "ordered": []}


def suggest(days_horizon: int = 14) -> dict:
    """Return a priority ordering for deadlines within ``days_horizon`` days."""
    tasks_md = vault.read_md(TASKS_FILE)
    proj_md = vault.read_md(PROJECT_INDEX_FILE)

    hard_dates = markdown.parse_hard_dates(tasks_md)

    today = date.today()
    horizon = today + timedelta(days=days_horizon)
    relevant = [d for d in hard_dates if d["date"] and today <= d["date"] <= horizon]

    if not relevant:
        return {
            "recommendation": f"No hard deadlines in the next {days_horizon} days.",
            "ordered": [],
        }

    deadline_lines = "\n".join(
        f"- {d['date'].isoformat()} ({(d['date'] - today).days}d): {d['label']}"
        for d in relevant
    )

    prompt = f"""David has these upcoming deadlines/milestones in the next {days_horizon} days. Today is {today.isoformat()}.

{deadline_lines}

Also: he has these active projects with their next steps:
{proj_md}

Recommend an order for which task David should tackle FIRST, considering:
- Hard deadlines (defense, send-to-client, payment due)
- Sequencing dependencies (e.g. defense prep depends on having the deck done; sending Ulli draft needs drafting time)
- Energy budget (don't expect heroics on event days or vacation days)
- Stakes (low-reversibility decisions like PKV vs high-stakes deliverables like defense)

Output as JSON only (no other text):
{{
  "recommendation": "1-2 sentence headline recommendation",
  "ordered": [
    {{"rank": 1, "task": "...", "deadline": "YYYY-MM-DD", "rationale": "1 sentence"}},
    ...
  ]
}}

Be specific. Don't repeat the deadline list — reorder it with reasoning.
"""

    try:
        result = run_claude(prompt, timeout=120)
    except Exception as exc:  # subprocess / timeout / CLI-missing — degrade gracefully
        logger.warning("priority_suggestor: claude call failed: %s", exc)
        return {
            "recommendation": "Could not generate a suggestion (Claude call failed).",
            "ordered": [],
        }

    match = re.search(r"\{.*\}", result, re.DOTALL)
    if not match:
        logger.warning("priority_suggestor: no JSON object in claude output")
        return {"recommendation": "Could not parse priority suggestion.", "ordered": []}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        logger.warning("priority_suggestor: JSON decode failed: %s", exc)
        return {"recommendation": "Could not parse priority suggestion.", "ordered": []}

    # Normalise to the expected shape so the frontend can rely on it.
    return {
        "recommendation": str(parsed.get("recommendation", "")),
        "ordered": parsed.get("ordered", []) or [],
    }
