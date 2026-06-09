"""Per-venture agent rosters — the "company of agents" model (Page 4, Layer B).

Each venture folder declares its agent roster in a config-driven manifest
(``_agents.json``). The dashboard reads it and renders Run buttons; agents run
on the existing background runner via :mod:`modules.agents.claude_cli`. Adding a
venture or an agent = edit a manifest, **no code change** (the locked Option-A
design, 2026-06-09).

Manifest schema (``<venture_folder>/_agents.json``)::

    {
      "venture": "K&E",                 # display name (informational)
      "updated": "2026-06-09",          # informational
      "agents": [
        {
          "key": "financial_model",     # unique within the manifest; [a-z0-9_]
          "label": "Financial Model Agent",
          "description": "One line shown on the run button.",
          "instructions": "The task prompt — what the agent should produce.",
          "context_files": ["README.md", "CLAUDE.md", "04_Buchhaltung_Steuern"],
          "allowed_tools": ["Read", "Glob", "Grep", "WebSearch", "WebFetch"],
          "cadence_days": null          # optional; older last-run ⇒ "due"
        }
      ]
    }

``context_files`` entries are paths **relative to the venture folder**; a
directory is expanded to its readable prioritized-extension files. The agent is
grounded in the venture's own folder (its ``CLAUDE.md`` carries the venture's
output style + hard rules), so every roster reads its own department.

**Vault-write safety:** like the idea validator, the agent's output is captured
from ``claude -p`` *stdout* and written by Python file I/O (OneDrive-safe per
the repo rule) — the CLI is given research tools only by default, never Write/
Edit, so it can't write vault files itself.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from core.config import get_logger
from modules.agents.background import BG_LOG_DIR
from modules.agents.claude_cli import run_claude
from modules.projects.workspace import (
    EXCLUDE_DIRS,
    PRIORITY_EXTENSIONS,
    project_root,
)

logger = get_logger(__name__)

MANIFEST_NAME = "_agents.json"
RUNS_SUBDIR = "_agent_runs"

# Default tools when a manifest agent doesn't specify its own. Research-only:
# the agent reads the folder + the web. Output is captured from stdout and
# written by Python (below), so the CLI never needs Write/Edit on the vault.
DEFAULT_ALLOWED_TOOLS = ["Read", "Glob", "Grep", "WebSearch", "WebFetch"]

# How many files to pull from a directory listed in context_files (newest first).
_DIR_FILE_LIMIT = 8
# Cap a single context file so one huge doc can't blow the prompt budget.
_MAX_FILE_CHARS = 40_000

_RUN_LABEL_PREFIX = "venture"


# --- Manifest I/O ------------------------------------------------------------
def manifest_path(project_id: str) -> Path:
    """Path to a venture's ``_agents.json`` (may not exist)."""
    return project_root(project_id) / MANIFEST_NAME


def read_manifest(project_id: str) -> dict | None:
    """Load a venture's manifest, or None if it has no roster yet."""
    path = manifest_path(project_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Unreadable manifest %s — treating as no roster", path, exc_info=True)
        return None
    data.setdefault("agents", [])
    return data


def write_manifest(project_id: str, manifest: dict) -> Path:
    """Write a venture's manifest via Python file I/O (OneDrive-safe).

    A ``.bak`` copy of any existing manifest is kept first, per the repo's
    vault-write rule.
    """
    path = manifest_path(project_id)
    if path.exists():
        path.with_suffix(path.suffix + ".bak").write_text(
            path.read_text(encoding="utf-8"), encoding="utf-8"
        )
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _find_agent(manifest: dict, agent_key: str) -> dict | None:
    return next((a for a in manifest.get("agents", []) if a.get("key") == agent_key), None)


# --- Last-run health (matched against background run_ids) --------------------
def run_label(project_id: str, agent_key: str) -> str:
    """Background-run label for a venture agent → ``venture_<id>_<key>``.

    The runner prefixes a timestamp, so the resulting run_id is
    ``<YYYYmmdd_HHMMSS>_venture_<id>_<key>`` — matched by substring below.
    """
    return f"{_RUN_LABEL_PREFIX}_{project_id}_{agent_key}"


def _run_timestamp(run: dict) -> datetime | None:
    for field in ("completed_at", "failed_at", "cancelled_at", "started_at"):
        raw = run.get(field)
        if raw:
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                continue
    try:
        return datetime.strptime(run["run_id"][:15], "%Y%m%d_%H%M%S")
    except (KeyError, ValueError):
        return None


def _latest_runs(project_id: str) -> dict[str, dict]:
    """Newest background run per agent key for this venture, by run_id substring."""
    latest: dict[str, dict] = {}
    if not BG_LOG_DIR.exists():
        return latest
    prefix = f"{_RUN_LABEL_PREFIX}_{project_id}_"
    for f in sorted(BG_LOG_DIR.glob("*.status.json"), key=lambda p: p.name):
        run_id = f.name.removesuffix(".status.json")
        idx = run_id.find(prefix)
        if idx == -1:
            continue
        agent_key = run_id[idx + len(prefix):]
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        data["run_id"] = run_id
        latest[agent_key] = data  # filenames sort chronologically → last wins = newest
    return latest


def list_agents(project_id: str) -> dict:
    """The venture's roster with per-agent last-run health.

    Returns ``{"venture": str|None, "has_manifest": bool, "agents": [...]}``.
    Health legend: ``ok`` ran recently / ``due`` cadence exceeded / ``failed``
    last run errored or was cancelled / ``never`` no run on record.
    """
    manifest = read_manifest(project_id)
    if manifest is None:
        return {"venture": None, "has_manifest": False, "agents": []}
    runs = _latest_runs(project_id)
    now = datetime.now()
    out = []
    for agent in manifest.get("agents", []):
        key = agent.get("key", "")
        run = runs.get(key)
        ts = _run_timestamp(run) if run else None
        cadence = agent.get("cadence_days")
        if run is None:
            health = "never"
        elif run.get("status") in {"failed", "cancelled"}:
            health = "failed"
        elif run.get("status") == "running":
            health = "ok"
        elif cadence and ts and (now - ts).days > cadence:
            health = "due"
        else:
            health = "ok"
        out.append({
            "key": key,
            "label": agent.get("label", key),
            "description": agent.get("description", ""),
            "cadence_days": cadence,
            "health": health,
            "last_run_at": ts.isoformat() if ts else None,
            "last_run_id": run.get("run_id") if run else None,
            "last_run_status": run.get("status") if run else None,
        })
    return {"venture": manifest.get("venture"), "has_manifest": True, "agents": out}


def run_history(project_id: str, limit: int = 30) -> list[dict]:
    """All background runs for this venture's agents, newest first."""
    if not BG_LOG_DIR.exists():
        return []
    prefix = f"{_RUN_LABEL_PREFIX}_{project_id}_"
    rows = []
    for f in BG_LOG_DIR.glob("*.status.json"):
        run_id = f.name.removesuffix(".status.json")
        idx = run_id.find(prefix)
        if idx == -1:
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        ts = _run_timestamp({**data, "run_id": run_id})
        rows.append({
            "run_id": run_id,
            "agent_key": run_id[idx + len(prefix):],
            "status": data.get("status"),
            "at": ts.isoformat() if ts else None,
            "result": data.get("result"),
            "error": data.get("error"),
        })
    rows.sort(key=lambda r: r["run_id"], reverse=True)
    return rows[:limit]


# --- Context assembly --------------------------------------------------------
def _readable(p: Path) -> str | None:
    if not p.is_file() or p.name.startswith("~$"):
        return None
    if p.suffix.lower() not in {".md", ".txt", ".json", ".csv"}:
        # Binary/Office docs can't be inlined as text — name them instead.
        return None
    try:
        body = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return body[:_MAX_FILE_CHARS]


def _gather_context(root: Path, context_files: list[str]) -> tuple[str, list[str]]:
    """Build the reference-context block + a list of binary files merely named.

    Each entry in ``context_files`` is resolved relative to the venture root.
    Readable text files are inlined; directories contribute their newest
    prioritized files; binary docs (docx/xlsx/pptx/pdf) are listed by name so
    the agent knows they exist and can ask David to open them.
    """
    parts: list[str] = []
    named_binaries: list[str] = []
    seen: set[Path] = set()

    def add_file(p: Path) -> None:
        rp = p.resolve()
        if rp in seen:
            return
        seen.add(rp)
        text = _readable(p)
        if text is not None:
            rel = p.relative_to(root) if root in p.parents or p.parent == root else p.name
            parts.append(f"\n## {rel}\n\n```\n{text}\n```\n")
        elif p.suffix.lower() in {ext for ext in PRIORITY_EXTENSIONS}:
            named_binaries.append(p.name)

    for entry in context_files:
        target = (root / entry).resolve()
        if not str(target).startswith(str(root.resolve())):
            continue  # never escape the venture folder
        if target.is_dir():
            if target.name in EXCLUDE_DIRS:
                continue
            cands: list[Path] = []
            for ext in PRIORITY_EXTENSIONS:
                cands += [
                    f for f in target.rglob(f"*{ext}")
                    if not any(part in EXCLUDE_DIRS for part in f.parts)
                    and not f.name.startswith("~$")
                ]
            cands.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            for f in cands[:_DIR_FILE_LIMIT]:
                add_file(f)
        elif target.exists():
            add_file(target)

    return "".join(parts), named_binaries


# --- Refusal guard (lightweight; agents produce drafts, not 1500-word docs) --
def _looks_like_refusal(output: str) -> bool:
    text = (output or "").strip()
    if len(text) < 40:
        return True
    low = text.lower()
    markers = (
        "i can't help", "i cannot help", "i won't fabricate", "cannot fabricate",
        "which venture", "which project do you", "i need more",
    )
    return len(text) < 600 and any(m in low for m in markers)


# --- The runner (invoked by the background runner) ---------------------------
def run_agent(project_id: str, agent_key: str) -> str:
    """Run one manifest agent for a venture and persist its output.

    Reads the venture's ``_agents.json``, grounds the agent in the configured
    context files, runs ``claude -p`` with the agent's allowed tools, then writes
    the captured output to ``<venture>/_agent_runs/<ts>_<key>.md`` via Python
    file I/O. Returns the output file path as a string (surfaced in the run
    status). Raises on a missing manifest/agent or a refusal-shaped reply
    (nothing is written in that case).
    """
    root = project_root(project_id)
    manifest = read_manifest(project_id)
    if manifest is None:
        raise FileNotFoundError(f"No {MANIFEST_NAME} in {root.name} — this venture has no roster.")
    agent = _find_agent(manifest, agent_key)
    if agent is None:
        raise KeyError(f"No agent '{agent_key}' in {root.name}/{MANIFEST_NAME}")

    context, named_binaries = _gather_context(root, agent.get("context_files", []))
    allowed_tools = agent.get("allowed_tools") or DEFAULT_ALLOWED_TOOLS
    binaries_note = (
        "\n\nThe following binary documents exist in the venture folder but are "
        "not inlined here (open them in the OS if you need their contents): "
        + ", ".join(named_binaries)
        if named_binaries else ""
    )

    prompt = f"""You are the **{agent.get('label', agent_key)}** for the venture "{manifest.get('venture', root.name)}".
You work as one agent in this venture's dedicated department. The venture's own
folder is your ground truth — its CLAUDE.md defines the output style and hard
rules you MUST follow, and its README defines current state and direction.

# YOUR JOB
{agent.get('instructions', '').strip()}

# GROUND RULES
- Stay grounded in the reference context below. Do not invent facts, figures, or
  strategic direction that aren't supported by the folder or live research.
- Where the folder lacks information you need (e.g. a business-model direction not
  yet locked, a number with no source), STOP and flag it as an OPEN QUESTION FOR
  DAVID rather than fabricating it. This respects David's global rule that
  original strategic thinking is his to do.
- Produce a single, well-structured Markdown document as your output.{binaries_note}

---

# REFERENCE CONTEXT (venture folder)
{context if context else "(no readable context files configured)"}

---

# OUTPUT
Produce your Markdown document now.
"""

    logger.info("Running venture agent %s/%s (tools=%s)", project_id, agent_key, ",".join(allowed_tools))
    output = run_claude(prompt, timeout=900, allowed_tools=allowed_tools)
    if _looks_like_refusal(output):
        raise RuntimeError(
            f"Agent '{agent_key}' for {root.name} returned a refusal/clarification reply "
            f"({len(output.strip())} chars), not a document. Nothing was written. "
            "Check the manifest instructions + context_files, then re-run."
        )

    runs_dir = root / RUNS_SUBDIR
    runs_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = runs_dir / f"{ts}_{agent_key}.md"
    header = (
        f"# {agent.get('label', agent_key)} — {manifest.get('venture', root.name)}\n\n"
        f"_Generated {datetime.now():%Y-%m-%d %H:%M} by the venture agent runner._\n\n---\n\n"
    )
    out_path.write_text(header + output.strip() + "\n", encoding="utf-8")
    return str(out_path)


# --- Starter manifest (for pursue-an-idea → Flow A venture) ------------------
def starter_manifest(venture_name: str) -> dict:
    """A generic Flow-A roster seeded when an idea is pursued into a venture.

    Three editable starter agents covering the validation-to-launch arc. David
    tunes the instructions/context per venture afterwards — the whole point of
    the config-driven model.
    """
    return {
        "venture": venture_name,
        "updated": f"{datetime.now():%Y-%m-%d}",
        "note": "Starter roster — edit instructions/context_files per this venture's real work.",
        "agents": [
            {
                "key": "market_research",
                "label": "Market & Competitor Research Agent",
                "description": "Refreshes market sizing + competitor scan from the folder + the web.",
                "instructions": (
                    "Research this venture's market and competitive landscape. Pull the "
                    "current state from the venture folder, then use web search to update "
                    "sizing, key players, and recent developments. Cite every external "
                    "claim. End with the 3 biggest open questions for David."
                ),
                "context_files": ["README.md", "CLAUDE.md"],
                "allowed_tools": DEFAULT_ALLOWED_TOOLS,
                "cadence_days": 30,
            },
            {
                "key": "financial_model",
                "label": "Financial Model Agent",
                "description": "Structures the financial model + assumptions; flags gaps.",
                "instructions": (
                    "Lay out the financial model structure for this venture: revenue "
                    "drivers, cost base, unit economics, and the key assumptions. Use only "
                    "numbers traceable to the folder; where an assumption is missing, flag "
                    "it as an open question for David rather than inventing it."
                ),
                "context_files": ["README.md", "CLAUDE.md"],
                "allowed_tools": ["Read", "Glob", "Grep"],
                "cadence_days": None,
            },
            {
                "key": "business_plan",
                "label": "Business Plan Agent",
                "description": "Drafts/updates the business plan skeleton from the folder.",
                "instructions": (
                    "Draft a business-plan skeleton for this venture grounded in the folder: "
                    "problem, solution, market, model, go-to-market, team, risks. Mark every "
                    "section that needs David's strategic input as an OPEN QUESTION rather "
                    "than fabricating his strategy."
                ),
                "context_files": ["README.md", "CLAUDE.md"],
                "allowed_tools": ["Read", "Glob", "Grep", "WebSearch", "WebFetch"],
                "cadence_days": None,
            },
        ],
    }


def write_starter_manifest(project_id: str, venture_name: str) -> Path:
    """Seed a starter ``_agents.json`` for a freshly-created Flow A venture.

    No-op (returns the existing path) if a manifest already exists, so re-running
    a pursue never clobbers a hand-tuned roster.
    """
    if read_manifest(project_id) is not None:
        return manifest_path(project_id)
    return write_manifest(project_id, starter_manifest(venture_name))


def is_safe_agent_key(key: str) -> bool:
    """Manifest keys are restricted to a safe charset (used in filenames/labels)."""
    return bool(re.fullmatch(r"[a-z0-9_]{1,64}", key or ""))
