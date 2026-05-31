"""Market Researcher agent — weekly research brief.

Orchestrates: load watchlist universe -> fetch fresh prices/news -> load prior
state (philosophy, hypotheses, last brief, captured tweets) -> build a long
synthesis prompt -> run it through ``claude -p`` -> write the brief and update
the Hypothesis Tracker.

Vault writes use Python file I/O only (per project rule) and snapshot a ``.bak``
before overwriting state files.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from pathlib import Path

from core.config import VAULT_PATH, get_logger
from modules.agents import data_sources
from modules.agents.claude_cli import run_claude
from modules.agents.watchlist_loader import load_universe

logger = get_logger(__name__)

INVESTING_DIR = VAULT_PATH / "4_Areas" / "Investing"
BRIEFS_DIR = INVESTING_DIR / "Market_Briefs"
TWEETS_DIR = INVESTING_DIR / "Captured_Tweets"
HYPOTHESIS_FILE = INVESTING_DIR / "Hypothesis_Tracker.md"
PHILOSOPHY_FILE = INVESTING_DIR / "Investment_Philosophy.md"


# ---------------------------------------------------------------------------
# Data gathering
# ---------------------------------------------------------------------------
def gather_data(universe: dict) -> dict:
    """Fetch fresh prices + news for the entire universe."""
    out: dict = {"snapshots": {}, "news": {}}
    all_tickers: list[str] = []
    for entry in universe["tier1"] + universe["tier2"]:
        if entry.get("ticker"):
            all_tickers.append(entry["ticker"])
    for theme_entries in universe["tier3"].values():
        for entry in theme_entries:
            if entry.get("ticker"):
                all_tickers.append(entry["ticker"])
    for tk in all_tickers:
        out["snapshots"][tk] = data_sources.price_snapshot(tk)
        out["news"][tk] = data_sources.ticker_news(tk, limit=8)
    return out


def load_state() -> dict:
    """Read prior state from vault files."""
    return {
        "hypothesis_tracker": HYPOTHESIS_FILE.read_text(encoding="utf-8")
        if HYPOTHESIS_FILE.exists()
        else "(no hypothesis tracker yet)",
        "philosophy": PHILOSOPHY_FILE.read_text(encoding="utf-8")
        if PHILOSOPHY_FILE.exists()
        else "(no investment philosophy doc yet)",
        "last_brief": _last_brief(),
        "captured_tweets_this_week": _tweets_this_week(),
    }


def _last_brief() -> str:
    if not BRIEFS_DIR.exists():
        return "(no prior brief)"
    files = sorted(BRIEFS_DIR.glob("*.md"), reverse=True)
    if not files:
        return "(no prior brief)"
    return files[0].read_text(encoding="utf-8")


def _tweets_this_week() -> str:
    today = date.today()
    iso_year, iso_week, _ = today.isocalendar()
    f = TWEETS_DIR / f"{iso_year}-W{iso_week:02d}.md"
    return f.read_text(encoding="utf-8") if f.exists() else "(no tweets captured this week)"


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------
def build_prompt(universe: dict, data: dict, state: dict) -> str:
    """Build the long synthesis prompt fed to ``claude -p``."""
    today = date.today()
    week_start = today - timedelta(days=6)

    return f"""You are an equity research analyst writing a weekly market brief for David Koch, an M&A analyst starting at Evercore on 2026-07-01. The brief covers the week of {week_start.isoformat()} to {today.isoformat()}.

# Style and structure rules

- Voice: crisp analyst, dense, scannable. Like a sell-side morning note.
- Length: 2,500-4,000 words. Detail over brevity. Always lead with executive summary.
- Every factual claim cites a source URL.
- Numbers tagged as either [filing] (from primary source) or [computed] (derived).
- Tone: critical, not promotional. Point out weaknesses, risks, contradictions.

# Output sections (use these exact H2 headers in order):

## 1. TL;DR
3 short bullets: dominant narrative, what moved David's direct exposure, THE ONE thing for next conversation.

## 2. Big Market News This Week
Beyond ticker-specific news. Central bank moves, trade/tariff developments, geopolitics, sector rotations, mega M&A deals (>$5B), IPOs, regulatory shocks. Each item: what happened, why it matters, who's affected from David's universe.

## 3. Macro Pulse
Table of 8 macro instruments: Friday close, week %, 30d %, 1-line note.

## 4. Your Holdings
One subsection per held name (GOOGL, BABA, BYDDY, SOL): weekly performance vs benchmark, material news/filings, material change vs thesis y/n, sources.

## 5. Watchlist Movers
Top 5 names from Tier 3 with biggest move or news. 2-3 lines each with reasoning.

## 6. Sector Themes
M&A activity (flag Evercore-advised deals), earnings upcoming next week, AI/semis, China policy, crypto regulation.

## 7. What This Really Means — Synthesis
The "so what?" layer. Connect this week's events to David's portfolio thesis, watchlist, and Investment Philosophy. 3-5 lines per major theme tied back to actual holdings.

## 8. Hypothesis Tracker
For each active hypothesis from prior state (see Hypothesis_Tracker below):
- Statement
- New supporting evidence this week
- New contradicting evidence this week
- Conviction: 1-5 score + direction since last week (up/down/flat)
- Status: ACTIVE / CONFIRMED / WEAKENED / RETIRED

If new hypotheses emerge from this week's events, propose them with: statement, why this week suggests it, what evidence would confirm/refute over time.

## 9. Potential Moves
NOT recommendations. Options for David's next discussion. For each:
- The move (e.g. "Trim BYDDY 30% on X")
- Trigger / rationale from this week
- Risks
- Sizing thought
- Status: needs decision

## 10. Twitter Insights Synthesis
If captured tweets exist this week, roll up themes and synthesize.

## 11. Daily Rollup
Mon / Tue / Wed / Thu / Fri. 3-5 key headlines + sources per day. Chronological.

## 12. Sources
Full URL list with dates pulled.

---

# REFERENCE STATE (read carefully — informs your synthesis)

## Investment Philosophy
{state['philosophy']}

## Hypothesis Tracker (prior state — UPDATE this section in your output's section 8)
{state['hypothesis_tracker']}

## Last Week's Brief (for continuity — call back to predictions/hypotheses where relevant)
{state['last_brief']}

## Captured Tweets This Week (David's curation — synthesize in section 10)
{state['captured_tweets_this_week']}

# UNIVERSE DEFINITION

{_format_universe(universe)}

# FRESH DATA THIS WEEK

{_format_data(data)}

# YOUR TASK

Write the full weekly Market Brief now using the exact section structure above. Begin with `# Market Brief — Week of {week_start.isoformat()} to {today.isoformat()}`. Output in Markdown.
"""


def _format_universe(universe: dict) -> str:
    parts = ["## Tier 1 — Macro pulse"]
    for e in universe["tier1"]:
        parts.append(f"- {e['label']}")
    parts.append("\n## Tier 2 — Direct exposure")
    for e in universe["tier2"]:
        parts.append(f"- {e['label']}")
    parts.append("\n## Tier 3 — Themed")
    for theme, entries in universe["tier3"].items():
        parts.append(f"\n### {theme}")
        for e in entries:
            parts.append(f"- {e['label']}")
    parts.append("\n## Themes watched")
    for t in universe["themes"]:
        parts.append(f"- {t}")
    return "\n".join(parts)


def _format_data(data: dict) -> str:
    parts = ["## Price snapshots\n"]
    for tk, snap in data["snapshots"].items():
        if "error" in snap:
            parts.append(f"- {tk}: data unavailable ({snap['error']})")
            continue
        parts.append(
            f"- {tk}: {snap.get('last_close', 'n/a')} {snap.get('currency', '')} | "
            f"week {snap.get('week_change_pct', 0):+.2f}% | "
            f"30d {snap.get('month_change_pct', 0):+.2f}%"
        )
    parts.append("\n## Recent headlines\n")
    for tk, news in data["news"].items():
        if news:
            parts.append(f"### {tk}")
            for n in news[:5]:
                parts.append(
                    f"- {n.get('title', '')} ({n.get('publisher', '')}, "
                    f"{n.get('publish_time', '')[:10]}) {n.get('link', '')}"
                )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Status helpers (for the dashboard)
# ---------------------------------------------------------------------------
def list_briefs(limit: int = 8) -> list[Path]:
    """Return up to ``limit`` brief files, newest first."""
    if not BRIEFS_DIR.exists():
        return []
    return sorted(BRIEFS_DIR.glob("*.md"), reverse=True)[:limit]


def last_run_date() -> date | None:
    """Return the date of the most recent brief (parsed from filename), or None."""
    briefs = list_briefs(limit=1)
    if not briefs:
        return None
    try:
        return date.fromisoformat(briefs[0].stem)
    except ValueError:
        return None


def next_run_datetime(now: datetime | None = None) -> datetime:
    """Return the next scheduled run: the upcoming Sunday at 19:00 local time.

    Schedule is fixed at Sunday 19:00 Europe/Berlin (see Windows Task Scheduler
    setup in the README). Computed in naive local time for display.
    """
    now = now or datetime.now()
    days_ahead = (6 - now.weekday()) % 7  # Monday=0 ... Sunday=6
    candidate = datetime.combine(now.date() + timedelta(days=days_ahead), time(19, 0))
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run() -> Path:
    """Full agent run. Returns the path of the brief file written."""
    INVESTING_DIR.mkdir(parents=True, exist_ok=True)
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    TWEETS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Market Researcher: loading universe")
    universe = load_universe()
    logger.info("Market Researcher: gathering data")
    data = gather_data(universe)
    state = load_state()
    prompt = build_prompt(universe, data, state)

    logger.info("Market Researcher: calling claude -p (this may take a few minutes)")
    brief_md = run_claude(prompt, timeout=900)

    today = date.today()
    brief_path = BRIEFS_DIR / f"{today.isoformat()}.md"
    brief_path.write_text(brief_md, encoding="utf-8")
    logger.info("Market Researcher: wrote brief to %s", brief_path)

    _update_hypothesis_tracker(brief_md)
    return brief_path


def _update_hypothesis_tracker(brief_md: str) -> None:
    """Extract section 8 of the brief and write it to Hypothesis_Tracker.md."""
    lines = brief_md.splitlines()
    in_section = False
    captured: list[str] = []
    for line in lines:
        if line.startswith("## 8. Hypothesis Tracker") or line.startswith(
            "## 8 Hypothesis Tracker"
        ):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            captured.append(line)

    if not captured:
        logger.warning("No Hypothesis Tracker section found in brief; leaving state file untouched")
        return

    if HYPOTHESIS_FILE.exists():
        bak = HYPOTHESIS_FILE.parent / (HYPOTHESIS_FILE.name + ".bak")
        bak.write_text(HYPOTHESIS_FILE.read_text(encoding="utf-8"), encoding="utf-8")

    content = (
        "# Hypothesis Tracker\n\n"
        f"Updated {date.today().isoformat()} by Market Researcher agent.\n\n"
        + "\n".join(captured).strip()
        + "\n"
    )
    HYPOTHESIS_FILE.write_text(content, encoding="utf-8")
    logger.info("Updated Hypothesis Tracker at %s", HYPOTHESIS_FILE)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    path = run()
    logger.info("Brief written: %s", path)
