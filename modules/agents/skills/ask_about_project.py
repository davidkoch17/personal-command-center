"""Ask Claude about a specific project. Loads project context."""
from __future__ import annotations

from modules.agents.claude_cli import run_claude_with_files
from modules.projects.workspace import key_files, project_root


def ask(project_id: str, question: str) -> str:
    """Ask a question with the project's key files loaded."""
    root = project_root(project_id)
    files = key_files(project_id, limit=5)
    readme = root / "README.md"
    if readme.exists() and readme not in files:
        files = [readme] + files
    prompt = f"""You are Claude assisting David with project {root.name}.
The reference files for this project are appended below.

David's question:
{question}

Respond clearly and concretely.
"""
    return run_claude_with_files(prompt, files, timeout=300)
