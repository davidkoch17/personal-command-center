"""Load ideas from 1_Projects/98_Ideen/."""
from pathlib import Path
import re
from core.config import PROJECTS_PATH


IDEEN_PATH = PROJECTS_PATH / "98_Ideen"


def list_ideas() -> list[dict]:
    """Return [{name, content, source_path}, ...] for each idea."""
    out = []
    if not IDEEN_PATH.exists():
        return out
    # Top-level .md files
    for f in sorted(IDEEN_PATH.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        name = _extract_h1(text) or f.stem.replace("_", " ")
        out.append({"name": name, "content": text, "source_path": str(f)})
    # Subdirectories
    for d in sorted(IDEEN_PATH.iterdir()):
        if d.is_dir():
            readme = d / "README.md"
            if readme.exists():
                text = readme.read_text(encoding="utf-8")
                name = _extract_h1(text) or d.name.replace("_", " ")
            else:
                text = f"(No README in {d.name})"
                name = d.name.replace("_", " ")
            out.append({"name": name, "content": text, "source_path": str(d)})
    return out


def _extract_h1(md: str) -> str | None:
    for line in md.splitlines():
        m = re.match(r"^#\s+(.+)$", line)
        if m:
            return m.group(1).strip()
    return None
