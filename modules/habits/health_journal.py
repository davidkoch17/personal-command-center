"""Read/write daily health journal entries in 4_Areas/Health_Fitness/Journal/."""
from pathlib import Path
from datetime import date
from core.config import VAULT_PATH

JOURNAL_DIR = VAULT_PATH / "4_Areas" / "Health_Fitness" / "Journal"
JOURNAL_DIR.mkdir(parents=True, exist_ok=True)


def _path_for(d: date) -> Path:
    return JOURNAL_DIR / f"{d.isoformat()}.md"


def save_entry(d: date, mood: int, energy: int, sleep_h: float,
               workout: str, diet: str, supplements: str, notes: str) -> Path:
    """Write/overwrite the entry for date d. Backs up previous if exists."""
    path = _path_for(d)
    if path.exists():
        backup = path.with_suffix(".md.bak")
        backup.write_bytes(path.read_bytes())
    content = (
        f"# Health journal — {d.isoformat()}\n\n"
        f"- Mood: {mood}/10\n"
        f"- Energy: {energy}/10\n"
        f"- Sleep: {sleep_h} h\n"
        f"- Workout: {workout}\n"
        f"- Diet: {diet}\n"
        f"- Supplements: {supplements}\n"
        f"\n## Notes\n\n{notes}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def read_today() -> dict | None:
    """Return parsed entry for today, or None if none exists."""
    path = _path_for(date.today())
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    # cheap parse — return the raw text plus best-effort fields
    return {"raw": text, "path": str(path)}


def list_recent(n: int = 14) -> list[Path]:
    """List up to n most recent entries by date desc."""
    files = sorted(JOURNAL_DIR.glob("*.md"), reverse=True)
    return files[:n]
