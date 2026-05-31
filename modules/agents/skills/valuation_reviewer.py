"""Valuation Reviewer skill — sanity-check a valuation against comparables."""
from __future__ import annotations

from modules.agents.claude_cli import run_claude


def review(ticker: str, your_valuation_summary: str, peers: list[str]) -> str:
    """Review the user's valuation logic. Returns a Markdown critique."""
    prompt = f"""You are a senior equity research analyst reviewing a junior analyst's valuation work on {ticker}.

The junior analyst's valuation summary:
---
{your_valuation_summary}
---

Peer set proposed: {', '.join(peers)}

Task: Produce a critical Markdown review with these sections:
1. Methodology check — is the approach right?
2. Comp set check — are the peers correct? Missing/extra?
3. Key multiples sanity check
4. Assumptions stress test — which assumptions are most fragile?
5. Counter-arguments to the analyst's conclusion
6. Overall: ACCEPT / CHALLENGE / REJECT with reasoning

Be tough but fair. Every claim cited if from external data.
"""
    return run_claude(prompt, timeout=600)
