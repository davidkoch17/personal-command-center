"""Decision journal — structured buy/sell/decision logs (Phase 15d, Category H).

One Markdown file per decision under
``4_Areas/Investing/Decision_Journal/YYYY-MM-DD_<ticker>_<action>.md`` in the
vault. Each file captures the full pre-trade structure (thesis, conviction,
emotion, expected outcome, risks, pre-mortem) plus a retrospective section that
is filled in 3-6 months later. The whole point is to make David's decisions
reviewable against their stated rationale — see Investment_Philosophy.md
Sections 12 (behavioral) and 16 (pre-mortem).

Vault I/O rule: these files live in the vault, so writes go through Python file
I/O (never the Edit/Write tool). Retrospective updates back up the file first via
``core.vault.write_md``.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from core import vault
from core.config import VAULT_PATH, get_logger

logger = get_logger(__name__)

JOURNAL_DIR = VAULT_PATH / "4_Areas" / "Investing" / "Decision_Journal"


def log_decision(
    ticker: str,
    action: str,  # buy/sell/add/trim
    quantity: float,
    price: float,
    rationale: str,
    conviction_score: int,    # 0-6, per Section 7.1
    emotion: str,             # "calm", "fomo", "fear", "greed", "boredom", etc.
    expected_return: float | None = None,
    expected_timeframe_months: int | None = None,
    thesis: str = "",
    risks: str = "",
    pre_mortem: str = "",      # See Section 16 — write failure narrative BEFORE acting
) -> Path:
    """Log a decision with full structure; returns the created file path."""
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today()
    safe_ticker = ticker.replace("/", "_").replace(".", "_")
    path = JOURNAL_DIR / f"{today.isoformat()}_{safe_ticker}_{action}.md"

    expected_return_str = f"{expected_return * 100:.1f}" if expected_return is not None else "TBD"
    content = f"""# Decision: {action.upper()} {ticker} — {today.isoformat()}

**Action:** {action}
**Ticker:** {ticker}
**Quantity:** {quantity}
**Price:** € {price:,.2f}
**Conviction:** {conviction_score}/6
**Emotion at time of decision:** {emotion}
**Logged at:** {datetime.now().isoformat()}

## Thesis
{thesis}

## Rationale
{rationale}

## Expected outcome
- Expected return: {expected_return_str}%
- Expected timeframe: {expected_timeframe_months} months

## Risks
{risks}

## Pre-mortem (failure narrative)
{pre_mortem}

## Retrospective (filled in later)
- **Was the thesis right?** _(fill in 3-6 months later)_
- **Did the outcome match expectations?** _(fill in)_
- **What did I get right / wrong?** _(fill in)_
- **Lesson:** _(fill in)_
"""
    path.write_text(content, encoding="utf-8")
    logger.info("Logged decision %s %s -> %s", action, ticker, path.name)
    return path


def list_decisions(limit: int = 50) -> list[dict]:
    """List recent decisions parsed into structured form (newest first)."""
    if not JOURNAL_DIR.exists():
        return []
    files = sorted(JOURNAL_DIR.glob("*.md"), reverse=True)[:limit]
    out = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        m_ticker = re.search(r"\*\*Ticker:\*\*\s+(\S+)", text)
        m_action = re.search(r"\*\*Action:\*\*\s+(\w+)", text)
        m_conv = re.search(r"\*\*Conviction:\*\*\s+(\d+)/6", text)
        m_emotion = re.search(r"\*\*Emotion at time of decision:\*\*\s+(\w+)", text)
        # A retrospective is "done" once the placeholder text is gone.
        has_retro = "_(fill in" not in text
        out.append({
            "filename": f.name,
            "date": f.stem.split("_")[0],
            "ticker": m_ticker.group(1) if m_ticker else None,
            "action": m_action.group(1) if m_action else None,
            "conviction": int(m_conv.group(1)) if m_conv else None,
            "emotion": m_emotion.group(1) if m_emotion else None,
            "has_retrospective": has_retro,
            "path": str(f),
        })
    return out


def get_decision(filename: str) -> dict | None:
    """Return one decision's full markdown body + parsed header fields."""
    path = JOURNAL_DIR / filename
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    parsed = next((d for d in list_decisions(limit=10_000) if d["filename"] == filename), None)
    return {"filename": filename, "content": text, **(parsed or {})}


def add_retrospective(filename: str, retro_text: str, was_right: bool) -> bool:
    """Update a decision file's retrospective section. Returns True on success."""
    path = JOURNAL_DIR / filename
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    new_retro = f"""## Retrospective (filled in {date.today().isoformat()})
- **Was the thesis right?** {"YES" if was_right else "NO"}
- **Reflection:** {retro_text}
"""
    content = re.sub(r"## Retrospective.*?(?=\n##|\Z)", new_retro, content, flags=re.DOTALL)
    vault.write_md(path, content)  # backs up the prior version first
    logger.info("Added retrospective to %s (was_right=%s)", filename, was_right)
    return True
