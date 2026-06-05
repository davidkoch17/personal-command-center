"""Wrapper around `claude -p` subprocess. Runs prompts on David's Max subscription.

Inference runs on the local Claude Code CLI (David's Claude Max subscription),
so there is no Anthropic API key and zero per-call cost. Calls are slow
(~10-60s, longer for large synthesis prompts) but free.

Implementation notes (Windows):
- The ``claude`` launcher is resolved to its full path via :func:`shutil.which`
  so the call works with ``shell=False`` (no fragile shell quoting of huge
  prompts).
- The prompt is fed on **stdin**, not as an argv element. Large briefs can run
  to tens of thousands of characters and would blow past the Windows
  command-line length limit if passed as an argument.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from core.config import get_logger

logger = get_logger(__name__)


def _resolve_claude() -> str:
    """Return the full path to the ``claude`` executable, or raise if missing."""
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError(
            "`claude` CLI not found in PATH. Verify the Claude Code installation "
            "(this agent runs inference via `claude -p` on David's Max subscription)."
        )
    return exe


def run_claude(
    prompt: str, timeout: int = 600, allowed_tools: list[str] | None = None
) -> str:
    """Run a prompt via Claude Code headless mode. Returns stdout.

    ``allowed_tools`` pre-authorizes tools via ``--allowed-tools`` (Item #78):
    headless runs can't answer permission prompts, so a tool that isn't
    pre-allowed is silently denied — which is how validator stages ended up
    producing training-knowledge-only output. Callers that need web research
    must pass the tools explicitly; the default (None) keeps the conservative
    no-extra-tools behavior for briefings/voice.
    """
    exe = _resolve_claude()
    cmd = [exe, "-p"]
    if allowed_tools:
        cmd += ["--allowed-tools", ",".join(allowed_tools)]
    logger.info(
        "Running claude -p (prompt %d chars, timeout %ds, allowed_tools=%s)",
        len(prompt), timeout, ",".join(allowed_tools) if allowed_tools else "-",
    )
    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed: {result.stderr}")
    return result.stdout


def run_claude_with_files(prompt: str, file_paths: list[Path], timeout: int = 600) -> str:
    """Like :func:`run_claude` but appends file contents with clear delimiters."""
    parts = [prompt, "\n\n---\n\n# Reference files\n"]
    for p in file_paths:
        if not p.exists():
            continue
        try:
            body = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Skipping unreadable file %s: %s", p, exc)
            continue
        parts.append(f"\n## {p.name}\n\n```\n{body}\n```\n")
    return run_claude("".join(parts), timeout=timeout)
