"""Read and append to Decision_Log.md."""
from pathlib import Path
from datetime import date
import re
import shutil
from core.config import SYSTEM_PATH


DECISION_LOG = SYSTEM_PATH / "Decision_Log.md"


def append_decision(d: date, title: str, context: str, decision: str,
                    rationale: str, tags: str) -> None:
    """Append a decision entry to Decision_Log.md."""
    if DECISION_LOG.exists():
        # Backup
        backup = DECISION_LOG.with_suffix(".md.bak")
        shutil.copy2(DECISION_LOG, backup)
        existing = DECISION_LOG.read_text(encoding="utf-8")
    else:
        existing = "# Decision Log\n\nRunning log of meaningful decisions.\n"
    entry = (
        f"\n## {d.isoformat()} — {title}\n\n"
        f"**Tags:** {tags}\n\n"
        f"### Context\n{context}\n\n"
        f"### Decision\n{decision}\n\n"
        f"### Rationale\n{rationale}\n"
    )
    DECISION_LOG.write_text(existing + entry, encoding="utf-8")


def list_decisions() -> list[dict]:
    """Parse Decision_Log.md into [{date, title, body}] entries, newest first."""
    if not DECISION_LOG.exists():
        return []
    text = DECISION_LOG.read_text(encoding="utf-8")
    # Split on H2
    entries = re.split(r"(?m)^## ", text)
    out = []
    for chunk in entries[1:]:  # skip preamble before first H2
        first_line, _, body = chunk.partition("\n")
        m = re.match(r"(\d{4}-\d{2}-\d{2})\s*—\s*(.+)", first_line.strip())
        if m:
            out.append({"date": m.group(1), "title": m.group(2), "body": body.strip()})
    return sorted(out, key=lambda x: x["date"], reverse=True)
