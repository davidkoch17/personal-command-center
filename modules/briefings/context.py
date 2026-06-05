"""Snapshot of David's world, used as prompt context for briefings.

Moved out of ``backend/api/voice.py`` (Item #16) so both the voice briefing
endpoint and the weekly briefing generator share one assembler — and so the
business logic lives in ``modules/``, per the layering rule in ``backend/main.py``.
"""
from __future__ import annotations

import re

from core.config import get_logger

logger = get_logger(__name__)


def assemble_briefing_context() -> str:
    """Gather a compact snapshot of David's world for a briefing prompt.

    Every source is best-effort: a missing file or unconfigured integration is
    skipped rather than failing the whole briefing.
    """
    from datetime import date

    from core import markdown, vault
    from core.config import PROJECT_INDEX_FILE, TASKS_FILE

    parts: list[str] = []

    today = date.today()
    parts.append(f"Today is {today.strftime('%A, %B %d, %Y')}.")

    # Open tasks for the near term — full task text, so the briefing can quote it.
    try:
        tasks_md = vault.read_md(TASKS_FILE)
        bullets = (
            markdown.parse_section_bullets(tasks_md, "This weekend")
            or markdown.parse_section_bullets(tasks_md, "Today")
            or markdown.parse_section_bullets(tasks_md, "This week")
            or []
        )
        unchecked = [b["text"] for b in bullets if not b["checked"]]
        if unchecked:
            parts.append("Open tasks (quote the exact text): " + "; ".join(unchecked[:6]))

        # Immovable real-world deadlines — exact dates, never "end of week".
        hard = [h for h in markdown.parse_hard_dates(tasks_md) if h.get("date")]
        if hard:
            dated = "; ".join(
                f"{h['date'].strftime('%a %b %d')}: {h['label']}" for h in hard[:5]
            )
            parts.append("Hard dates (use the exact date): " + dated)
    except Exception:  # noqa: BLE001 - briefing context is best-effort
        logger.debug("briefing: tasks unavailable", exc_info=True)

    # Portfolio snapshot — name the held tickers, not just a count.
    try:
        from modules.finance.portfolio import combined_holdings, summary_metrics

        m = summary_metrics()
        parts.append(
            f"Portfolio value: EUR {m['total_value']:.0f}, {m['position_count']} "
            f"positions, latest snapshot {m.get('latest_snapshot')}."
        )
        try:
            df = combined_holdings()
            names = [str(n) for n in df.get("Name", []) if str(n).strip()][:8]
            if names:
                parts.append("Held positions: " + ", ".join(names))
        except Exception:  # noqa: BLE001
            logger.debug("briefing: holdings unavailable", exc_info=True)
    except Exception:  # noqa: BLE001
        logger.debug("briefing: portfolio unavailable", exc_info=True)

    # Active decision alerts (Home_Redesign_Spec.md §2b) — so Jarvis can say
    # "You have 2 decisions pending — rebalance, concentration breach".
    try:
        import warnings

        from modules.finance import decision_support as ds

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            s = ds.decision_summary()
        active = (
            s.get("rebalance_count", 0)
            + s.get("concentration_count", 0)
            + s.get("harvest_count", 0)
        )
        if active:
            parts.append(
                f"Decision alerts ({active} active — mention these): "
                f"{s.get('rebalance_count', 0)} rebalance, "
                f"{s.get('concentration_count', 0)} concentration, "
                f"{s.get('harvest_count', 0)} tax-loss harvest."
            )
    except Exception:  # noqa: BLE001
        logger.debug("briefing: decision alerts unavailable", exc_info=True)

    # Active project statuses + next steps — include the literal folder names so
    # the briefing can say "Ulli (03_Project_Ulli_Acebuche)" not "your project".
    try:
        proj_md = vault.read_md(PROJECT_INDEX_FILE)
        projects = markdown.parse_projects(proj_md)
        active = [p for p in projects if "done" not in (p.get("status_text") or "").lower()]
        if active:
            named = "; ".join(
                f"{p['folder']} — next: {p.get('next_step') or '(no next step)'}"
                for p in active[:4]
            )
            parts.append(
                f"Active projects ({len(active)}) — use these literal folder names: {named}"
            )
    except Exception:  # noqa: BLE001
        logger.debug("briefing: projects unavailable", exc_info=True)

    # Watchlist universe tickers — so the briefing names tickers, not "the market".
    try:
        from core.config import WATCHLIST_UNIVERSE_FILE

        watchlist_md = vault.read_md(WATCHLIST_UNIVERSE_FILE)
        tickers = sorted(set(re.findall(r"\(([A-Z0-9.\-^]+(?:=[A-Z]+)?)\)", watchlist_md)))
        if tickers:
            parts.append("Watchlist tickers (name tickers, not 'the market'): " + ", ".join(tickers[:20]))
    except Exception:  # noqa: BLE001
        logger.debug("briefing: watchlist unavailable", exc_info=True)

    # Most recent market brief.
    try:
        from modules.agents.market_researcher import BRIEFS_DIR

        latest = sorted(BRIEFS_DIR.glob("*.md"), reverse=True)
        if latest:
            parts.append(f"Latest market brief: {latest[0].stem}.")
    except Exception:  # noqa: BLE001
        logger.debug("briefing: market briefs unavailable", exc_info=True)

    return "\n".join(parts)
