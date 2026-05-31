"""Auto-drafted weekly review."""
from datetime import datetime, timedelta
from pathlib import Path
from core.config import SYSTEM_PATH
from modules.projects.activity import recent_files, activity_summary
from modules.projects.journal import list_decisions


WEEKLY_REVIEWS_DIR = SYSTEM_PATH / "Weekly_Reviews"


def draft_this_week() -> str:
    """Generate a markdown draft of this week's review."""
    today = datetime.now().date()
    week_start = today - timedelta(days=6)
    counts = activity_summary(days=7)
    recent = recent_files(limit=10, days=7)
    decisions_this_week = [d for d in list_decisions() if d["date"] >= week_start.isoformat()]

    md = [f"# Weekly Review — {today.isoformat()}", ""]
    md += [f"Week of {week_start.isoformat()} to {today.isoformat()}", ""]
    md += ["## Activity by area", ""]
    for area, count in sorted(counts.items(), key=lambda x: -x[1]):
        md += [f"- {area}: {count} files touched"]
    md += ["", "## Files touched", ""]
    for r in recent:
        md += [f"- {r['mtime'].strftime('%Y-%m-%d')} — {r['name']}"]
    md += ["", "## Decisions this week", ""]
    if decisions_this_week:
        for d in decisions_this_week:
            md += [f"- {d['date']} — {d['title']}"]
    else:
        md += ["- (none logged)"]
    md += ["", "## Reflection (fill in)", "", "- What went well: ", "- What didn't: ", "- Next week focus: "]
    return "\n".join(md)


def save_weekly_review(content: str) -> Path:
    WEEKLY_REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().date()
    path = WEEKLY_REVIEWS_DIR / f"{today.isoformat()}.md"
    path.write_text(content, encoding="utf-8")
    return path
