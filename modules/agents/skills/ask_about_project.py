"""Ask Claude about a specific project. Loads project context."""
from __future__ import annotations

from core.config import SYSTEM_PATH
from modules.agents.claude_cli import run_claude, run_claude_with_files
from modules.projects.workspace import key_files, project_root


def ask_anything(question: str, timeout: int = 60) -> str:
    """General Q&A with David's vault system files as context.

    Loads the personal-memory / project-index / task-command-center notes so the
    answer is grounded in David's actual context. Used by the Home "Quick Run"
    panel: it runs synchronously with a short ``timeout`` (the caller falls back
    to a background run on :class:`subprocess.TimeoutExpired`).
    """
    candidates = [
        SYSTEM_PATH / "Personal_Memory.md",
        SYSTEM_PATH / "Project_Index.md",
        SYSTEM_PATH / "Task_Command_Center.md",
    ]
    files = [f for f in candidates if f.exists()]
    prompt = f"""You are Claude assisting David. The reference files below are his
personal command-center system notes (memory, project index, tasks). Use them as
context where relevant.

David's question:
{question}

Answer clearly and concretely. If the answer isn't in the context, say so and
answer from general knowledge.
"""
    if files:
        return run_claude_with_files(prompt, files, timeout=timeout)
    return run_claude(prompt, timeout=timeout)


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
