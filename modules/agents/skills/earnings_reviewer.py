"""Earnings Reviewer skill — read transcript + filings, summarize material changes."""
from __future__ import annotations

from modules.agents import data_sources
from modules.agents.claude_cli import run_claude


def review(ticker: str, transcript_text: str | None = None) -> str:
    """Run an earnings review for ``ticker``. Returns Markdown."""
    news = data_sources.ticker_news(ticker, limit=15)
    snap = data_sources.price_snapshot(ticker)

    prompt = f"""You are an equity research analyst reviewing the most recent earnings release for {ticker}.

Task: Read the materials below and produce a Markdown earnings review with these sections:
1. Headline numbers (vs consensus, vs prior year)
2. What surprised positively
3. What surprised negatively
4. Guidance changes
5. Management tone (if transcript available)
6. Impact on thesis / valuation
7. Action implication for David's position (HOLD / ADD / TRIM / RESEARCH MORE)

Tone: critical analyst, dense, every claim cited.

# Price context
{snap}

# Recent news
{news}

# Earnings transcript (if provided)
{transcript_text or '(no transcript provided)'}

Output the review now in Markdown.
"""
    return run_claude(prompt, timeout=600)
