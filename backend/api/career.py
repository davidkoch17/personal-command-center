"""Career API — onboarding/technicals checklists + career prep skills."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException

from backend.models.schemas import CareerSkillRequest, CareerChecklistToggleRequest
from core.config import EVERCORE_START_DATE
from modules.career import tracker
from modules.agents import background

router = APIRouter()

CAREER_SKILLS_MODULE = "modules.agents.skills.career"

# Skill name -> how many args (besides nothing) it takes from the request.
#   1-arg: pass [arg]; 2-arg: pass [arg, context]; mock_interview defaults arg.
_CAREER_SKILLS = {
    "quiz_technicals": ("arg",),         # module
    "mock_interview": ("arg_opt",),      # kind (defaults to "technical")
    "deal_note": ("arg",),               # article_text
    "model_checker": ("arg",),           # model_summary
    "industry_primer": ("arg",),         # sector
    "career_letter_draft": ("arg", "context"),  # kind, context
}


def _counts() -> dict:
    onboarding = tracker.read_onboarding()
    technicals = tracker.read_technicals()
    return {
        "onboarding_done": sum(1 for i in onboarding if i["checked"]),
        "onboarding_total": len(onboarding),
        "technicals_done": sum(1 for i in technicals if i["checked"]),
        "technicals_total": len(technicals),
    }


@router.get("")
def overview() -> dict:
    """Countdown to the Evercore start date + checklist completion counts."""
    try:
        start = date.fromisoformat(EVERCORE_START_DATE)
        days_until = (start - date.today()).days
    except ValueError:
        start, days_until = None, None
    return {
        "start_date": EVERCORE_START_DATE,
        "days_until_start": days_until,
        **_counts(),
    }


@router.get("/workspace")
def workspace() -> dict:
    """Full career workspace: onboarding + technicals checklist items."""
    return {
        "start_date": EVERCORE_START_DATE,
        "onboarding": tracker.read_onboarding(),
        "technicals": tracker.read_technicals(),
        **_counts(),
    }


@router.get("/activity")
def activity(limit: int = 8) -> dict:
    """Recent file activity in ``3_Career/`` (newest first)."""
    limit = max(1, min(limit, 30))
    return {"items": tracker.recent_activity(limit=limit)}


@router.get("/model")
def model() -> dict:
    """Status of the Evercore 3-statement model (Cowork build → Excel file)."""
    return tracker.model_status()


@router.post("/checklist/toggle")
def toggle_checklist(req: CareerChecklistToggleRequest) -> dict:
    """Toggle one onboarding or technicals checklist item by index."""
    if req.checklist == "onboarding":
        items = tracker.read_onboarding()
        save = tracker.save_onboarding
    else:
        items = tracker.read_technicals()
        save = tracker.save_technicals
    if not (0 <= req.index < len(items)):
        raise HTTPException(status_code=400, detail="Checklist index out of range.")
    items[req.index]["checked"] = not items[req.index]["checked"]
    save(items)
    return {"ok": True, "checked": items[req.index]["checked"]}


@router.post("/skill")
def run_skill(req: CareerSkillRequest) -> dict:
    """Run a career prep skill in the background (quiz, mock interview, etc.)."""
    if req.skill not in _CAREER_SKILLS:
        raise HTTPException(status_code=400, detail=f"Unknown career skill: {req.skill}")
    spec = _CAREER_SKILLS[req.skill]
    args: list = []
    for slot in spec:
        if slot == "arg":
            if not (req.arg or "").strip():
                raise HTTPException(status_code=400, detail=f"'{req.skill}' requires the 'arg' field.")
            args.append(req.arg.strip())
        elif slot == "arg_opt":
            args.append((req.arg or "technical").strip())
        elif slot == "context":
            args.append(req.context or "")
    info = background.launch(
        module_path=CAREER_SKILLS_MODULE, callable_name=req.skill,
        args=args, label=f"Career {req.skill}",
    )
    return {"ok": True, "run_id": info["run_id"]}
