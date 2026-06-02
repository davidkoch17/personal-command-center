"""AI assistant for week planning recommendations."""
import json
import re
from datetime import date

from modules.agents.claude_cli import run_claude


def recommend_placements(pool: list, week_data: dict, calendar_overlay: dict, hard_dates: list) -> dict:
    """Claude recommends optimal placement for unassigned pool tasks based on:
    - Deadline urgency (hard dates)
    - Project importance
    - Time estimates (if available)
    - Calendar availability per day
    - Current load on each day
    """
    today = date.today().isoformat()

    prompt = f"""You are David's planning assistant. Help him distribute open tasks across this week.

Today: {today}

POOL (open tasks needing assignment):
{json.dumps([{'id': t['id'], 'text': t['text'], 'source': t['source_label']} for t in pool[:30]], indent=2)}

CURRENT WEEK ASSIGNMENTS:
{json.dumps({k: [e for e in week_data.get(k, [])] for k in ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']}, indent=2)}

CALENDAR PER DAY (David's existing commitments):
{json.dumps(calendar_overlay, indent=2)}

HARD DATES THIS WEEK:
{json.dumps(hard_dates, indent=2)}

Consider:
- Hard deadlines closest first
- Don't overload days with calendar events
- Group related tasks (same project → same morning)
- Friday afternoons + Sunday evenings tend to be low-energy — light tasks
- Important + urgent → today/tomorrow morning
- Important + not urgent → mid-week
- Routine admin → end-of-day windows

Return JSON only:
{{
  "recommendations": [
    {{
      "task_id": "abc123",
      "task_text": "Short text",
      "suggested_day": "wednesday",
      "rationale": "1-2 sentence why this day"
    }},
    ...
  ],
  "warnings": ["Optional flags — e.g. 'Friday is overloaded with calendar events, light load suggested'"],
  "summary": "1-sentence overview"
}}

Recommend placement for ALL pool items. If a task should not be scheduled this week (e.g., long-term thing), put it in suggested_day = "later" and explain.
"""
    result = run_claude(prompt, timeout=120)
    match = re.search(r"\{.*\}", result, re.DOTALL)
    if not match:
        return {"recommendations": [], "warnings": ["Could not parse AI response"], "summary": ""}
    return json.loads(match.group(0))
