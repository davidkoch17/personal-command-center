"""Hypothesis hit-rate retrospective (Phase 15d, Category H — Section 15).

Reviews closed hypotheses from the ``Hypothesis_Tracker.md`` vault file and
computes a hit rate (CONFIRMED / total closed). A "closed" hypothesis is one
whose body carries a CONFIRMED, WEAKENED or RETIRED status marker. This is the
quantitative companion to the qualitative decision journal: it answers "when I
form a thesis, how often am I right?".
"""
from __future__ import annotations

import re

from core import vault
from core.config import VAULT_PATH, get_logger

logger = get_logger(__name__)

HYPOTHESIS_FILE = VAULT_PATH / "4_Areas" / "Investing" / "Hypothesis_Tracker.md"


def hit_rate_review(quarters_back: int = 4) -> dict:
    """Review closed hypotheses. Compute aggregate hit rate.

    ``quarters_back`` is accepted for API symmetry / future date-filtering; the
    tracker rarely dates closure, so today every closed hypothesis is counted.
    """
    if not HYPOTHESIS_FILE.exists():
        return {"hypotheses_reviewed": 0, "confirmed": 0, "weakened": 0,
                "hit_rate": None, "details": [], "quarters_back": quarters_back}

    text = vault.read_md(HYPOTHESIS_FILE)
    closed: list[dict] = []
    sections = re.split(r"(?m)^## ", text)
    for section in sections[1:]:
        first_line, _, body = section.partition("\n")
        if "RETIRED" in body or "CONFIRMED" in body or "WEAKENED" in body:
            m = re.match(r"\d{4}-\d{2}-\d{2}\s*[—-]\s*([A-Z0-9.\-]+)", first_line.strip())
            if m:
                status_match = re.search(r"Status:\s*(\w+)", body)
                closed.append({
                    "ticker": m.group(1),
                    "status": status_match.group(1) if status_match else "UNKNOWN",
                    "raw": body[:500],
                })

    confirmed = [h for h in closed if h["status"] == "CONFIRMED"]
    weakened = [h for h in closed if h["status"] == "WEAKENED"]

    return {
        "hypotheses_reviewed": len(closed),
        "confirmed": len(confirmed),
        "weakened": len(weakened),
        "hit_rate": len(confirmed) / len(closed) if closed else None,
        "details": closed,
        "quarters_back": quarters_back,
    }
