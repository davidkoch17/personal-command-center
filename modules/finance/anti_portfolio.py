"""Anti-portfolio — names considered but NOT bought (Phase 15d, Section 14).

Append-only log at ``4_Areas/Investing/Anti_Portfolio.md``. Reviewed annually to
surface skip-bias: the skips that, in hindsight, were mistakes. Each entry
records the bull/bear case and the reason for passing, with an outcome line to
fill in 12-24 months later.
"""
from __future__ import annotations

import re
from datetime import date

from core import vault
from core.config import VAULT_PATH, get_logger

logger = get_logger(__name__)

ANTI_PORTFOLIO_FILE = VAULT_PATH / "4_Areas" / "Investing" / "Anti_Portfolio.md"

_HEADER = "# Anti-Portfolio\n\nNames considered but not bought. Reviewed annually for skip-bias.\n"


def log_skip(ticker: str, name: str, considered_date: date, price: float,
             bull_case: str, bear_case: str, reason: str) -> None:
    """Log a ticker that was considered but not bought (append-only)."""
    existing = vault.read_md(ANTI_PORTFOLIO_FILE) if ANTI_PORTFOLIO_FILE.exists() else _HEADER

    entry = f"""
## {considered_date.isoformat()} — {ticker} ({name})

**Price at consideration:** € {price:,.2f}
**Reason for skip:** {reason}

### Bull case
{bull_case}

### Bear case
{bear_case}

### Outcome (filled in later)
- _(Was the skip right? Fill in 12-24 months later.)_
"""
    vault.write_md(ANTI_PORTFOLIO_FILE, existing + entry)
    logger.info("Logged anti-portfolio skip: %s", ticker)


def list_skips() -> list[dict]:
    """Parse the anti-portfolio file into structured entries (newest first)."""
    if not ANTI_PORTFOLIO_FILE.exists():
        return []
    text = vault.read_md(ANTI_PORTFOLIO_FILE)
    out: list[dict] = []
    for section in re.split(r"(?m)^## ", text)[1:]:
        first_line, _, body = section.partition("\n")
        m = re.match(r"(\d{4}-\d{2}-\d{2})\s*[—-]\s*([A-Z0-9.\-]+)\s*\(([^)]*)\)", first_line.strip())
        if not m:
            continue
        price_m = re.search(r"Price at consideration:\*\*\s*€\s*([\d,.]+)", body)
        reason_m = re.search(r"Reason for skip:\*\*\s*(.+)", body)
        out.append({
            "considered_date": m.group(1),
            "ticker": m.group(2),
            "name": m.group(3).strip(),
            "price": float(price_m.group(1).replace(",", "")) if price_m else None,
            "reason": reason_m.group(1).strip() if reason_m else None,
        })
    return sorted(out, key=lambda e: e["considered_date"], reverse=True)


def annual_review(today: date | None = None) -> list[dict]:
    """Return entries considered 12-24 months ago — due for a skip-bias review."""
    today = today or date.today()
    due: list[dict] = []
    for entry in list_skips():
        try:
            d = date.fromisoformat(entry["considered_date"])
        except ValueError:
            continue
        months_ago = (today.year - d.year) * 12 + (today.month - d.month)
        if 12 <= months_ago <= 24:
            due.append({**entry, "months_ago": months_ago})
    return due
