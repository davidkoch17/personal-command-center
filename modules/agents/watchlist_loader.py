"""Parse 4_Areas/Investing/Watchlist.md into a structured universe."""
from __future__ import annotations

import re

from core.config import VAULT_PATH, get_logger

logger = get_logger(__name__)

WATCHLIST_PATH = VAULT_PATH / "4_Areas" / "Investing" / "Watchlist.md"

# Matches a ticker inside parentheses, e.g. "Apple (AAPL)" -> AAPL,
# "EUR/USD (EURUSD=X)" -> EURUSD=X, "S&P 500 (^GSPC)" -> ^GSPC.
_TICKER_RE = re.compile(r"\(([\^A-Z0-9.\-]+(?:=[A-Z]+)?)\)")


def load_universe() -> dict:
    """Return ``{tier1: [...], tier2: [...], tier3: {theme: [...]}, themes: [...]}``."""
    universe: dict = {"tier1": [], "tier2": [], "tier3": {}, "themes": []}
    if not WATCHLIST_PATH.exists():
        logger.info("No watchlist file at %s", WATCHLIST_PATH)
        return universe

    text = WATCHLIST_PATH.read_text(encoding="utf-8")
    current_tier: str | None = None
    current_theme: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Tier 1"):
            current_tier, current_theme = "tier1", None
        elif stripped.startswith("## Tier 2"):
            current_tier, current_theme = "tier2", None
        elif stripped.startswith("## Tier 3"):
            current_tier, current_theme = "tier3", None
        elif stripped.startswith("## Themes"):
            current_tier, current_theme = "themes", None
        elif stripped.startswith("### ") and current_tier == "tier3":
            current_theme = stripped[4:].strip()
            universe["tier3"][current_theme] = []
        elif stripped.startswith("- ") and current_tier:
            m = _TICKER_RE.search(stripped)
            ticker = m.group(1) if m else None
            label = stripped[2:].strip()
            entry = {"label": label, "ticker": ticker}
            if current_tier == "tier3":
                if current_theme:
                    universe["tier3"][current_theme].append(entry)
            elif current_tier == "themes":
                universe["themes"].append(label)
            else:
                universe[current_tier].append(entry)

    return universe
