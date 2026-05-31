"""Model Builder skill — generate a basic 3-statement model spec from inputs."""
from __future__ import annotations

from modules.agents.claude_cli import run_claude


def build(ticker: str, latest_filings_summary: str, assumptions: dict | str) -> str:
    """Generate a model outline. Returns Markdown describing the model + formulas."""
    prompt = f"""You are an equity research analyst building a 3-statement financial model for {ticker}.

Inputs:
- Latest filings summary: {latest_filings_summary}
- David's assumptions: {assumptions}

Task: Output a Markdown document that contains:
1. Model architecture (sheets, naming convention)
2. Revenue build — drivers, growth assumptions, segment split
3. Cost structure — line items, margin assumptions
4. Key working capital + capex
5. Three statements in narrative form (IS, BS, CFS year 1-5)
6. Valuation: DCF skeleton (WACC, terminal, value per share) AND comps cross-check
7. Sensitivity table outline (revenue growth × margin)
8. Flagged risks to the model

Output is a SPEC for David to then build in Excel. Be specific on formulas where it matters.
"""
    return run_claude(prompt, timeout=600)
