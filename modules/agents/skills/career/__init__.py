"""Career workspace skills (Phase 9b).

Evercore-prep helpers: technicals quizzing, mock interviews, deal notes, model
checking, sector primers, and career letters. All run via ``claude -p`` and work
foreground or via background.launch.
"""
from __future__ import annotations

from core import vault
from core.config import PERSONAL_MEMORY_FILE
from modules.agents.claude_cli import run_claude


def _memory() -> str:
    md = vault.read_md(PERSONAL_MEMORY_FILE)
    return md or "(no Personal_Memory.md found)"


def quiz_technicals(module: str) -> str:
    """Generate a short quiz (with answers) on a technicals module."""
    prompt = f"""You are an IB interview coach. Quiz David on the topic: "{module}".

Output Markdown:
1. 6-8 questions ramping from fundamentals to tricky edge cases
2. A collapsible-style "Answers" section after, with crisp model answers
Keep it bulge-bracket realistic.
"""
    return run_claude(prompt, timeout=600)


def mock_interview(kind: str = "technical") -> str:
    """Run a mock interview (behavioral or technical) — questions + ideal answers."""
    prompt = f"""You are an Evercore interviewer running a {kind} mock interview for David.

Context about David:
{_memory()}

Output Markdown:
1. 8-10 {kind} questions in realistic sequence
2. For each: what a strong answer contains + a common pitfall
3. A few curveballs
"""
    return run_claude(prompt, timeout=600)


def deal_note(article_text: str) -> str:
    """Turn a pasted deal article into a structured deal-note practice doc."""
    prompt = f"""Convert this deal article into a structured M&A deal note for practice.

# Article
{article_text}

Output Markdown:
- Parties & roles (acquirer / target / advisors)
- Deal structure (consideration, premium, financing)
- Strategic rationale
- Valuation read (multiples if available)
- Accretion/dilution intuition
- Risks / regulatory angles
- 3 questions an analyst should ask
Cite figures from the article; flag what's missing.
"""
    return run_claude(prompt, timeout=600)


def model_checker(model_summary: str) -> str:
    """Review a described 3-statement model for likely errors / weak spots."""
    prompt = f"""You are a senior banker reviewing a junior's 3-statement model. The junior describes it below
(or pastes key formulas / outputs). Find errors and weak assumptions.

# Model description
{model_summary}

Output Markdown:
1. Likely mechanical errors (balance sheet ties, circularity, signs)
2. Questionable assumptions
3. Missing items
4. Sanity-check ranges it should hit
5. Prioritized fix list
"""
    return run_claude(prompt, timeout=600)


def industry_primer(sector: str) -> str:
    """Quick sector primer for deal context."""
    prompt = f"""Write a concise industry primer on the "{sector}" sector for an incoming M&A analyst.

Use web search for current data. Output Markdown:
1. Value chain & key players
2. Economics & margins
3. Key drivers and cycle
4. Common deal rationales & recent M&A
5. Valuation conventions / typical multiples
6. What to watch in 2026
Cite sources.
"""
    return run_claude(prompt, timeout=600)


def career_letter_draft(kind: str, context: str) -> str:
    """Draft a cover letter / LinkedIn outreach / thank-you note."""
    prompt = f"""Draft a {kind} for David in his authentic, professional-but-human voice.

# Context about David
{_memory()}

# Specifics for this letter
{context}

Output the letter in Markdown, ready to edit. Keep it concise and specific — no fluff.
"""
    return run_claude(prompt, timeout=300)
