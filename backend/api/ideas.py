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
from modules.projects import agents as venture_agents, workspace

router = APIRouter()

RUNNER_MODULE = "modules.agents.skills.idea_validator.runner"
_STAGE_KEYS = {k for k, _, _ in iv.STAGES}


def _running_stage(state: dict) -> str | None:
    """Stage key currently in flight, from the runner's `_running` marker."""
    return (state.get("_running") or {}).get("stage_key")


def _stage_status(state: dict, stage_key: str) -> str:
    if _running_stage(state) == stage_key:
        return "running"
    s = state.get(stage_key)
    if not s:
        return "pending"
    return "stale" if s.get("stale") else "done"


def _next_stage(state: dict) -> str | None:
    """First stage that still needs running (missing or stale), in pipeline order."""
    for stage_key, _, _ in iv.STAGES:
        entry = state.get(stage_key)
        if not entry or entry.get("stale"):
            return stage_key
    return None


def _stage_quality(exists: bool, content: str) -> str:
    """Flag a stage's output: ``missing`` · ``corrupted`` (refusal) · ``valid``.

    Reuses the runner's refusal heuristic so the pipeline strip shows the same
    judgement the runner uses to reject bad output — a corrupted stage is one
    where a refusal/clarification reply was written instead of a real doc.
    """
    if not exists:
        return "missing"
    return "corrupted" if iv._looks_like_refusal(content) else "valid"


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
            next_stage=_next_stage(i.get("state", {})),
        )
        for i in iv.list_ideas()
    ]


@router.get("/killed")
def killed_ideas() -> list[dict]:
    """Killed ideas archived under ``98_Ideen/_killed/`` (collapsed section)."""
    return [{"name": k["name"], "reason": k["reason"]} for k in iv.list_killed()]


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
            "quality": _stage_quality(out_path.exists(), content),
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
        "running_stage": _running_stage(state),
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


@router.post("/{name}/run-remaining")
def run_remaining(name: str) -> dict:
    """Trigger only the missing/stale stages in the background.

    Resumes a half-finished pipeline without re-paying for completed stages
    (unlike ``run-all``, which re-runs everything).
    """
    _resolve(name)
    info = background.launch(
        module_path=RUNNER_MODULE, callable_name="run_remaining",
        args=[name], label=f"Validate {name} remaining",
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

    if req.decision == "Pursue":
        # Flow A: spin up a real venture folder with a starter agent roster.
        # The idea's validated artifacts stay in 98_Ideen and are referenced
        # from the new venture's README seed.
        seed = (
            f"Pursued from idea `{name}` on {datetime.now():%Y-%m-%d}. "
            f"Validation artifacts: `1_Projects/98_Ideen/{folder.name}/` "
            f"(brief, market study, business model, financial model, scorecard, MASTER)."
        )
        venture = workspace.create_project(name, "Flow A", seed=seed)
        venture_id = venture.name.split("_", 1)[0]
        manifest_path = venture_agents.write_starter_manifest(venture_id, name)
        vault.write_md(
            master,
            existing + note + f"\nSpun up Flow A venture: `1_Projects/{venture.name}/` "
            f"(starter agent roster at `{manifest_path.name}`).\n",
        )
        return {
            "ok": True, "decision": req.decision,
            "venture_folder": venture.name, "venture_id": venture_id,
        }

    vault.write_md(master, existing + note)
    return {"ok": True, "decision": req.decision}


@router.post("/{name}/overrides")
def update_overrides(name: str, req: IdeaOverridesRequest) -> dict:
    """Replace the idea's _overrides.md (read & respected by every stage prompt)."""
    folder = _resolve(name)
    vault.write_md(folder / "_overrides.md", req.text)
    return {"ok": True}
