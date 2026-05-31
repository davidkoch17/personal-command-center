"""Workflow templates."""
from pathlib import Path
from datetime import datetime
from core.config import SYSTEM_PATH
from modules.projects.workspace import project_root


TEMPLATES_DIR = SYSTEM_PATH / "Templates"


def list_templates() -> list[Path]:
    if not TEMPLATES_DIR.exists():
        return []
    return sorted(TEMPLATES_DIR.glob("*.md"))


def instantiate_template(template_name: str, project_id: str, doc_name: str) -> Path:
    """Copy a template into the project folder with a timestamped name."""
    src = TEMPLATES_DIR / f"{template_name}.md"
    if not src.exists():
        raise FileNotFoundError(src)
    proot = project_root(project_id)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    safe_name = doc_name.replace(" ", "_").replace("/", "-")
    dest = proot / f"{ts}_{safe_name}.md"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest
