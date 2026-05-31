"""Vault reader. Reads David's Obsidian vault MD files."""
from pathlib import Path
from datetime import datetime
import shutil


def read_md(path: Path) -> str:
    """Read a Markdown file as plain text. Returns empty string if missing."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def list_files(directory: Path, pattern: str = "*.md") -> list[Path]:
    """List matching files in a directory (non-recursive). Sorted by mtime desc."""
    if not directory.exists():
        return []
    files = list(directory.glob(pattern))
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def write_md(path: Path, content: str) -> None:
    """Write a Markdown file, backing up the previous version first."""
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
    path.write_text(content, encoding="utf-8")


def append_to_inbox(content: str, source: str = "quickcapture") -> Path:
    """Append a captured snippet to the inbox as a new timestamped MD file."""
    from core.config import INBOX_PATH
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = INBOX_PATH / f"{ts}_{source}.md"
    path.write_text(content, encoding="utf-8")
    return path
