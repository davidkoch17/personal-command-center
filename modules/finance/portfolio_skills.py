"""Claude-powered Portfolio workspace skills (Phase 9b).

Each skill builds a prompt from the live holdings snapshot plus the user's input
and runs it through ``claude -p`` (zero API cost). All are plain module-level
functions so they work both foreground (imported + called) and background
(handed to :func:`modules.agents.background.launch`).
"""
from __future__ import annotations

import shutil
from datetime import datetime

from core.config import (
    HYPOTHESIS_TRACKER_FILE,
    INVESTMENT_PHILOSOPHY_FILE,
    get_logger,
)
from modules.agents.claude_cli import run_claude
from modules.agents import data_sources
from modules.finance import portfolio

logger = get_logger(__name__)


def _holdings_context() -> str:
    """A compact text snapshot of current holdings for prompt context."""
    try:
        df = portfolio.combined_holdings()
        metrics = portfolio.summary_metrics()
    except Exception as exc:  # noqa: BLE001
        return f"(holdings unavailable: {exc})"
    lines = [
        f"Total value: €{metrics.get('total_value') or 0:,.0f} · "
        f"{metrics.get('position_count', 0)} positions · "
        f"snapshot {metrics.get('latest_snapshot')}"
    ]
    if not df.empty:
        for _, r in df.iterrows():
            lines.append(
                f"- {r.get('Name')} ({r.get('Type')}): qty {r.get('Quantity')}, "
                f"value €{r.get('Value (€)')}"
            )
    return "\n".join(lines)


def _philosophy() -> str:
    if INVESTMENT_PHILOSOPHY_FILE.exists():
        return INVESTMENT_PHILOSOPHY_FILE.read_text(encoding="utf-8")
    return "(no investment philosophy file found)"


def scenario(scenario_description: str) -> str:
    """What-if portfolio modeling (sell X, market -20%, FX move, add to TICKER)."""
    prompt = f"""You are a portfolio strategist running a what-if scenario for David's personal portfolio.

# Current holdings
{_holdings_context()}

# Investment philosophy (respect this)
{_philosophy()}

# Scenario to model
{scenario_description}

Task: produce a Markdown analysis covering, as relevant:
- Cash impact (€) and resulting cash position
- Allocation shift (before → after, by asset class)
- Concentration / risk impact
- German tax impact (Abgeltungsteuer 26.375%, 12-month rule where relevant)
- Recovery-time intuition for drawdown scenarios
- A clear bottom-line: what the numbers say, and the one risk to watch

Show your arithmetic. Flag anything that needs a Steuerberater. Be concrete with €.
"""
    return run_claude(prompt, timeout=600)


def quarterly_portfolio_review() -> str:
    """Generate a full written quarterly portfolio review document."""
    tracker = ""
    if HYPOTHESIS_TRACKER_FILE.exists():
        tracker = HYPOTHESIS_TRACKER_FILE.read_text(encoding="utf-8")
    prompt = f"""You are writing David's quarterly portfolio review.

# Current holdings
{_holdings_context()}

# Investment philosophy
{_philosophy()}

# Hypothesis tracker
{tracker or '(none)'}

Task: produce a complete Markdown review:
1. Executive summary (3-4 lines)
2. Performance & allocation read
3. Hypothesis scorecard — which theses played out, which broke
4. Concentration / risk flags
5. What to add / trim / hold, with reasoning
6. Open questions for next quarter

Critical, concise, every external claim cited.
"""
    return run_claude(prompt, timeout=900)


def why_is_x_moving(ticker: str, context: str = "") -> str:
    """Research + explain why a ticker is moving (uses recent news + web search)."""
    news = data_sources.combined_news(ticker, limit=10)
    snap = data_sources.price_snapshot(ticker)
    prompt = f"""You are an equity analyst. Explain, with evidence, why {ticker} is moving.

# Price context
{snap}

# Recent headlines
{news}

# David's added context
{context or '(none)'}

Task (Markdown):
1. The move (magnitude, timeframe)
2. Most likely drivers, ranked, each with a cited source
3. Signal vs noise — is this fundamental or sentiment/flow?
4. Thesis impact for a holder
Use web search to confirm. Cite every claim.
"""
    return run_claude(prompt, timeout=600)


def rebalance_suggestor(target_allocation: str) -> str:
    """Compare current vs target allocation and suggest trades."""
    prompt = f"""You are a portfolio manager proposing a rebalance for David.

# Current holdings
{_holdings_context()}

# Target allocation (David's input)
{target_allocation}

Task (Markdown):
1. Current vs target allocation table (by asset class / name)
2. Drift — where the book is over/under weight
3. Suggested trades to reach target (buy/sell €, in tax-aware order)
4. Tax considerations (German Abgeltungsteuer, 12-month holding)
5. One-line summary of the rebalance intent
Show the arithmetic.
"""
    return run_claude(prompt, timeout=600)


def add_hypothesis(ticker: str, hypothesis: str) -> str:
    """Append a hypothesis for a name to the Hypothesis_Tracker (vault write + .bak)."""
    ticker = (ticker or "").strip().upper()
    hypothesis = (hypothesis or "").strip()
    if not ticker or not hypothesis:
        return "Nothing added — ticker and hypothesis are both required."
    path = HYPOTHESIS_TRACKER_FILE
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Hypothesis Tracker\n"
    if path.exists():
        shutil.copy2(path, path.with_suffix(".md.bak"))
    stamp = datetime.now().strftime("%Y-%m-%d")
    entry = (
        f"\n**[{ticker}] (added {stamp}, David)** — {hypothesis}\n"
        f"- *Conviction:* (set)\n- *Status:* **ACTIVE (new).**\n"
    )
    path.write_text(existing.rstrip("\n") + "\n" + entry, encoding="utf-8")
    return f"Added hypothesis for {ticker} to Hypothesis_Tracker.md."
