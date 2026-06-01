"""Ideas API — wraps the 12-stage idea-validation runner.

Stage runs and full validation are long ``claude -p`` calls, so they always go
through the background runner and return a ``run_id`` immediately.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    IdeaCard, IdeaCreateRequest, StageRunRequest, IdeaDecisionRequest, IdeaOverridesRequest,
)
from core import vault
from modules.agents.skills.idea_validator import runner as iv
from modules.agents import background

router = APIRouter()

RUNNER_MODULE = "modules.agents.skills.idea_validator.runner"
_STAGE_KEYS = {k for k, _, _ in iv.STAGES}


def _stage_status(state: dict, stage_key: str) -> str:
    s = state.get(stage_key)
    if not s:
        return "pending"
    return "stale" if s.get("stale") else "done"


def _resolve(idea_name: str):
    """Return the idea folder if it exists as an active idea, else 404."""
    active = {i["path"].resolve(): i for i in iv.list_ideas()}
    folder = iv.idea_folder(idea_name)
    if folder.resolve() not in active:
        raise HTTPException(status_code=404, detail=f"Unknown idea: {idea_name}")
    return folder


@router.get("")
def list_ideas() -> list[IdeaCard]:
    """List active idea cards with completion progress."""
    n_stages = len(iv.STAGES)
    return [
        IdeaCard(
            name=i["name"],
            stages_complete=i["stages_complete"],
            progress=min(i["stages_complete"], n_stages),
            state=i.get("state", {}),
        )
        for i in iv.list_ideas()
    ]


@router.post("")
def create_idea(req: IdeaCreateRequest) -> dict:
    """Create a new idea folder + brief; subsequent stages run on demand."""
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Idea name is required.")
    folder = iv.create_idea(req.name.strip(), req.brief_text)
    return {"ok": True, "name": folder.name, "path": str(folder)}


@router.get("/{name}")
def idea_workspace(name: str) -> dict:
    """Workspace state: per-stage status + output content, brief, overrides, MASTER."""
    folder = _resolve(name)
    state = iv._read_state(folder)
    stages = []
    for stage_key, slug, filename in iv.STAGES:
        out_path = folder / filename
        content = ""
        mtime = None
        if out_path.exists():
            try:
                content = out_path.read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001
                content = ""
            mtime = datetime.fromtimestamp(out_path.stat().st_mtime).isoformat()
        stages.append({
            "stage_key": stage_key,
            "slug": slug,
            "title": slug.replace("_", " ").title(),
            "filename": filename,
            "status": _stage_status(state, stage_key),
            "exists": out_path.exists(),
            "mtime": mtime,
            "content": content,
        })
    done = sum(1 for s in stages if s["status"] == "done")

    def _read(fname: str) -> str:
        p = folder / fname
        return p.read_text(encoding="utf-8") if p.exists() else ""

    return {
        "name": name,
        "stages_complete": done,
        "total_stages": len(iv.STAGES),
        "stages": stages,
        "brief": _read("01_Idea_Brief.md"),
        "overrides": _read("_overrides.md"),
        "master": _read("MASTER.md"),
    }


@router.post("/{name}/run-stage")
def run_stage(name: str, req: StageRunRequest) -> dict:
    """Trigger a single validation stage in the background."""
    _resolve(name)
    if req.stage_key not in _STAGE_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown stage_key: {req.stage_key}")
    info = background.launch(
        module_path=RUNNER_MODULE, callable_name="run_stage",
        args=[name, req.stage_key], label=f"Stage {req.stage_key} {name}",
    )
    return {"ok": True, "run_id": info["run_id"]}


@router.post("/{name}/run-all")
def run_all(name: str) -> dict:
    """Trigger the full Stage 2-12 validation in the background."""
    _resolve(name)
    info = background.launch(
        module_path=RUNNER_MODULE, callable_name="run_all",
        args=[name], label=f"Validate {name}",
    )
    return {"ok": True, "run_id": info["run_id"]}


@router.post("/{name}/decide")
def decide(name: str, req: IdeaDecisionRequest) -> dict:
    """Commit a Pursue/Park/Kill decision (Kill archives the idea)."""
    folder = _resolve(name)
    if req.decision == "Kill":
        if not req.reason.strip():
            raise HTTPException(status_code=400, detail="A kill reason is required.")
        iv.kill_idea(name, req.reason.strip())
        return {"ok": True, "killed": True}
    master = folder / "MASTER.md"
    note = f"\n\n## Decision\n{req.decision} — {datetime.now():%Y-%m-%d %H:%M}\n\n{req.reason.strip()}\n"
    existing = master.read_text(encoding="utf-8") if master.exists() else ""
    vault.write_md(master, existing + note)
    return {"ok": True, "decision": req.decision}


@router.post("/{name}/overrides")
def update_overrides(name: str, req: IdeaOverridesRequest) -> dict:
    """Replace the idea's _overrides.md (read & respected by every stage prompt)."""
    folder = _resolve(name)
    vault.write_md(folder / "_overrides.md", req.text)
    return {"ok": True}
