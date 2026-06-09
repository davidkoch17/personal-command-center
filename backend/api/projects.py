"""Projects API — wraps Project_Index.md + modules.projects.workspace."""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    ProjectCard, ProjectLogEntry, ProjectNextStepToggleRequest, ProjectCreateRequest,
)
from core import vault, markdown
from core.config import PROJECT_INDEX_FILE
from modules.agents import background
from modules.projects import agents, workspace

router = APIRouter()

_FLOW_RE = re.compile(r"\*\*Type:\*\*\s*Flow\s*([AB])", re.IGNORECASE)


def _parse_flow(readme: str) -> str | None:
    """Read the ``**Type:** Flow A/B`` line a created project's README carries."""
    m = _FLOW_RE.search(readme or "")
    return m.group(1).upper() if m else None

_STATUS_MAP = {
    "ON TRACK": "on_track",
    "NEEDS ATTENTION": "needs_attention",
    "AT RISK": "at_risk",
    "DONE": "done",
}


def _status_key(proj: dict) -> str:
    label, _ = markdown.status_display(proj)
    return _STATUS_MAP.get(label, "unknown")


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s.strip())
    except (ValueError, AttributeError):
        return None


def _big_milestone(milestones: list[dict]) -> dict | None:
    """Soonest upcoming dated milestone, else the most recent past, else first."""
    if not milestones:
        return None
    dated = [(m, _parse_date(m.get("date"))) for m in milestones]
    dated = [(m, d) for m, d in dated if d is not None]
    if dated:
        today = date.today()
        upcoming = sorted([(m, d) for m, d in dated if d >= today], key=lambda x: x[1])
        if upcoming:
            return upcoming[0][0]
        return sorted(dated, key=lambda x: x[1])[-1][0]
    return milestones[0]


def _file_info(p: Path) -> dict:
    exists = p.exists()
    return {
        "path": str(p),
        "name": p.name,
        "mtime": datetime.fromtimestamp(p.stat().st_mtime).isoformat() if exists else None,
        "exists": exists,
    }


def _projects() -> list[dict]:
    return markdown.parse_projects(vault.read_md(PROJECT_INDEX_FILE))


@router.get("")
def list_projects() -> list[ProjectCard]:
    """Project cards with status, big milestone, and the first open next step."""
    cards: list[ProjectCard] = []
    for proj in _projects():
        try:
            root = workspace.project_root(proj["id"])
            readme = vault.read_md(root / "README.md")
        except FileNotFoundError:
            readme = ""
        milestones = workspace.parse_milestones(readme)
        steps = workspace.parse_next_steps(readme)
        open_steps = [s for s in steps if not s["checked"]]
        big = _big_milestone(milestones)
        cards.append(ProjectCard(
            id=proj["id"],
            name=proj["name"].replace("_", " "),
            status=_status_key(proj),
            status_emoji=proj.get("status_emoji") or "",
            status_text=proj.get("status_text") or "",
            big_milestone=big["text"] if big else None,
            big_milestone_date=_parse_date(big.get("date")) if big else None,
            next_step=(open_steps[0]["text"] if open_steps else proj.get("next_step") or None),
            folder=proj.get("folder", ""),
            flow=_parse_flow(readme),
            has_agents=agents.manifest_path(proj["id"]).exists() if _root_ok(proj["id"]) else False,
        ))
    return cards


def _root_ok(project_id: str) -> bool:
    try:
        workspace.project_root(project_id)
        return True
    except FileNotFoundError:
        return False


@router.get("/{project_id}")
def project_workspace(project_id: str) -> dict:
    """Full workspace state: milestones, next steps, key files, subfolders, drafts, README.

    ``project_id`` may be the numeric id (``"03"``) or the full folder name
    (``"03_Project_Ulli_Acebuche"``) that Jarvis navigation URLs use — the latter
    is matched back to its project by the numeric prefix.
    """
    by_id = {p["id"]: p for p in _projects()}
    proj = by_id.get(project_id)
    if proj is None:
        # Full folder name like "03_Project_Ulli_Acebuche" → match by prefix.
        prefix = project_id.split("_", 1)[0]
        proj = by_id.get(prefix)
    if proj is None:
        raise HTTPException(status_code=404, detail=f"Unknown project id: {project_id}")
    try:
        root = workspace.project_root(proj["id"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    pid = proj["id"]
    readme = vault.read_md(root / "README.md")
    return {
        "id": pid,
        "name": proj["name"].replace("_", " "),
        "status": _status_key(proj),
        "status_text": proj.get("status_text") or "",
        "folder": proj.get("folder", ""),
        "milestones": workspace.parse_milestones(readme),
        "next_steps": workspace.parse_next_steps(readme),
        "key_files": [_file_info(p) for p in workspace.parse_key_files(readme, root)],
        "subfolders": [d.name for d in workspace.list_subfolders(pid)],
        "drafts": [
            {**d, "modified": d["modified"].isoformat() if hasattr(d.get("modified"), "isoformat") else d.get("modified")}
            for d in workspace.list_drafts(pid)
        ],
        "readme_md": readme,
    }


@router.post("/{project_id}/log")
def append_log(project_id: str, entry: ProjectLogEntry) -> dict:
    """Append a session note to the project's Project_Log.md."""
    try:
        path = workspace.append_project_log(project_id, entry.note)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True, "path": str(path)}


@router.post("/{project_id}/next-step/toggle")
def toggle_next_step(project_id: str, req: ProjectNextStepToggleRequest) -> dict:
    """Toggle a next-step checkbox in the project README by line index."""
    try:
        new_state = workspace.toggle_next_step(project_id, req.line_index)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if new_state is None:
        raise HTTPException(status_code=400, detail="Line is not a toggleable next step.")
    return {"ok": True, "new_state": new_state}


@router.post("")
def create_project(req: ProjectCreateRequest) -> dict:
    """Create a new project folder (Flow A or B) with a seeded README."""
    path = workspace.create_project(req.name, req.flow, req.seed)
    return {"ok": True, "path": str(path), "folder": path.name}


# --- Venture agent roster (Page 4, Layer B — config-driven manifests) --------
@router.get("/{project_id}/agents")
def venture_agents(project_id: str) -> dict:
    """The venture's agent roster (from ``_agents.json``) with last-run health."""
    try:
        return agents.list_agents(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{project_id}/agents/{agent_key}/run")
def run_venture_agent(project_id: str, agent_key: str) -> dict:
    """Launch a venture agent on the background runner; returns its run_id.

    The agent is defined entirely in the venture's manifest — no code change is
    needed to add or edit one. The run is labelled ``venture_<id>_<key>`` so the
    venture's run history can find it.
    """
    try:
        manifest = agents.read_manifest(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"No agent roster for {project_id}.")
    if not any(a.get("key") == agent_key for a in manifest.get("agents", [])):
        raise HTTPException(status_code=404, detail=f"No agent '{agent_key}' in this venture.")
    info = background.launch(
        module_path="modules.projects.agents", callable_name="run_agent",
        args=[project_id, agent_key], label=agents.run_label(project_id, agent_key),
    )
    return {"ok": True, "run_id": info["run_id"], "agent_key": agent_key}


@router.get("/{project_id}/runs")
def venture_runs(project_id: str, limit: int = 30) -> dict:
    """Run history for this venture's agents (newest first)."""
    return {"runs": agents.run_history(project_id, limit=limit)}
