"""Watchlist / per-ticker research skills (Phase 9b).

Adds three Claude-powered skills on top of the existing Phase 5 reviewers
(earnings, valuation, model). All run via ``claude -p`` and work foreground or
background.
"""
from __future__ import annotations

from modules.agents.claude_cli import run_claude
from modules.agents import data_sources
from modules.investing import research


def summarize_filing(ticker: str, filing_url: str) -> str:
    """Summarize an SEC filing given its URL."""
    prompt = f"""You are an equity analyst summarizing an SEC filing for {ticker}.

Filing URL: {filing_url}

Use web search to read the filing. Produce a Markdown summary:
1. Filing type & period
2. Headline financials (vs prior period)
3. Material changes / new disclosures
4. Risk-factor changes
5. What it means for the thesis
Cite specific sections. If you cannot access the URL, say so plainly.
"""
    return run_claude(prompt, timeout=600)


def compare_to_peers(ticker: str, peers: list[str] | str) -> str:
    """Build a comparables table for a name vs its peer set."""
    if isinstance(peers, str):
        peer_list = [p.strip() for p in peers.replace(",", " ").split() if p.strip()]
    else:
        peer_list = peers
    snap = data_sources.price_snapshot(ticker)
    prompt = f"""You are building a comparables table for {ticker} vs peers: {', '.join(peer_list) or '(none given)'}.

# Price context for {ticker}
{snap}

Use web search for current multiples. Produce a Markdown comp table with columns:
Ticker | Mkt Cap | P/E | P/S | EV/EBITDA | Rev growth | Gross margin | Op margin
Then:
1. Where {ticker} screens cheap/expensive vs the set
2. Justified or not, and why
3. One-line relative-value read
Cite sources for the multiples.
"""
    return run_claude(prompt, timeout=600)


def generate_thesis_statement(ticker: str, name: str = "") -> str:
    """Draft a clean thesis statement from the accumulated research notes."""
    notes = research.read_position_note(ticker)
    hyps = research.filter_hypotheses(ticker, name)
    prompt = f"""You are distilling David's research on {ticker} ({name}) into a clean investment thesis.

# Position notes
{notes or '(none yet)'}

# Active hypotheses
{chr(10).join(hyps) or '(none)'}

Task (Markdown):
1. One-sentence thesis
2. Why it could work (3 bullets)
3. Why it could fail (3 bullets)
4. What would confirm / refute it (measurable)
5. Suggested conviction (1-5) with reasoning
Tight and honest — no hype.
"""
    return run_claude(prompt, timeout=600)
