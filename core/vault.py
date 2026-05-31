"""Vault reader. Phase 1 stubs — phase 2 implements."""
from pathlib import Path


def read_md(path: Path) -> str:
    """Read a Markdown file as plain text. Phase 2 will add parsing."""
    raise NotImplementedError("Implemented in phase 2")


def list_files(directory: Path, pattern: str = "*.md") -> list[Path]:
    """List matching files in a directory. Phase 2 will implement."""
    raise NotImplementedError("Implemented in phase 2")
