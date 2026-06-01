"""Brand API — Content Studio pipeline, per-video workspaces, brand skills."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import BrandVideoCreateRequest, BrandSkillRequest
from modules.brand import videos
from modules.agents import background

router = APIRouter()

BRAND_SKILLS_MODULE = "modules.agents.skills.brand"

# Skill name -> whether it needs a free-text question argument.
_BRAND_SKILLS = {
    "generate_hook_variants": False,
    "draft_first_pass_script": False,
    "generate_shot_list": False,
    "generate_title_variants": False,
    "generate_description_tags": False,
    "generate_thumbnail_copy": False,
    "ask_claude_about_video": True,
}

# Slug (e.g. "concept") -> ("01_Concept.md", "Concept").
_SECTION_LOOKUP = {
    fname.split("_", 1)[1].rsplit(".", 1)[0].lower(): (fname, title)
    for fname, title in videos.SECTIONS
}


@router.get("")
def pipeline() -> dict:
    """Videos grouped by pipeline stage (kanban view)."""
    by_stage: dict[str, list[dict]] = {s: [] for s in videos.STAGES}
    for v in videos.list_videos():
        card = {
            "name": v["name"],
            "title": v["title"],
            "platform": v["platform"],
            "stage": v["stage"],
            "posting_date": v["posting_date"],
            "modified": v["modified"].isoformat() if hasattr(v["modified"], "isoformat") else v["modified"],
        }
        by_stage.setdefault(v["stage"], []).append(card)
    return {"stages": videos.STAGES, "by_stage": by_stage}


@router.get("/all/{section}")
def horizontal_slice(section: str) -> dict:
    """A single section (concept / script / titles / ...) across all videos."""
    key = section.lower()
    if key not in _SECTION_LOOKUP:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown section '{section}'. Options: {sorted(_SECTION_LOOKUP)}",
        )
    filename, title = _SECTION_LOOKUP[key]
    rows = []
    for v in videos.list_videos():
        rows.append({
            "name": v["name"],
            "title": v["title"],
            "stage": v["stage"],
            "content": videos.read_section(v["path"], filename),
        })
    return {"section": key, "title": title, "filename": filename, "videos": rows}


@router.post("/videos")
def create_video(req: BrandVideoCreateRequest) -> dict:
    """Create a new video folder with the 10 staged section files."""
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="Video title is required.")
    try:
        folder = videos.create_video(req.title.strip(), req.platform, req.concept)
    except FileExistsError:
        raise HTTPException(status_code=409, detail="A video with that title already exists.")
    return {"ok": True, "name": folder.name, "path": str(folder)}


@router.get("/videos/{name}")
def video_workspace(name: str) -> dict:
    """Per-video workspace: status front-matter + all section contents."""
    folder = videos.video_folder(name)
    if not folder.exists():
        raise HTTPException(status_code=404, detail=f"Unknown video: {name}")
    status = videos.read_status(folder)
    sections = [
        {"filename": fname, "title": title, "content": videos.read_section(folder, fname)}
        for fname, title in videos.SECTIONS
    ]
    return {"name": name, "status": status, "stages": videos.STAGES, "sections": sections}


@router.post("/videos/{name}/skill")
def run_skill(name: str, req: BrandSkillRequest) -> dict:
    """Run a brand skill for this video in the background (returns run_id)."""
    folder = videos.video_folder(name)
    if not folder.exists():
        raise HTTPException(status_code=404, detail=f"Unknown video: {name}")
    if req.skill not in _BRAND_SKILLS:
        raise HTTPException(status_code=400, detail=f"Unknown brand skill: {req.skill}")
    needs_question = _BRAND_SKILLS[req.skill]
    if needs_question:
        if not (req.question or "").strip():
            raise HTTPException(status_code=400, detail="This skill requires a question.")
        args = [name, req.question.strip()]
    else:
        args = [name]
    info = background.launch(
        module_path=BRAND_SKILLS_MODULE, callable_name=req.skill,
        args=args, label=f"Brand {req.skill} {name}",
    )
    return {"ok": True, "run_id": info["run_id"]}
