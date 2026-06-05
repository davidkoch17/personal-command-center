"""Generic skill launcher — routes a skill name to its module/callable.

Every skill runs in the background (Phase 10a: skills are long ``claude -p``
calls). The endpoint returns a ``run_id`` immediately; poll ``GET /api/runs/{id}``
or subscribe to the run's WebSocket for progress.
"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.models.schemas import SkillRunRequest
from modules.agents import background
from modules.agents.background import BG_LOG_DIR

router = APIRouter()

_REQUIRED = object()  # sentinel: parameter has no default and must be supplied

# skill name -> (module_path, callable_name, [(param_name, default), ...])
# Default of ``_REQUIRED`` means the caller must include it in ``args``.
SKILL_REGISTRY: dict[str, tuple[str, str, list[tuple[str, object]]]] = {
    # Market research
    "market_researcher": ("modules.agents.market_researcher", "run", []),
    # Equity skills
    "earnings_reviewer": (
        "modules.agents.skills.earnings_reviewer", "review",
        [("ticker", _REQUIRED), ("transcript_text", None)],
    ),
    "valuation_reviewer": (
        "modules.agents.skills.valuation_reviewer", "review",
        [("ticker", _REQUIRED), ("your_valuation_summary", _REQUIRED), ("peers", _REQUIRED)],
    ),
    "model_builder": (
        "modules.agents.skills.model_builder", "build",
        [("ticker", _REQUIRED), ("latest_filings_summary", _REQUIRED), ("assumptions", _REQUIRED)],
    ),
    # Watchlist skills
    "summarize_filing": (
        "modules.agents.skills.watchlist_skills", "summarize_filing",
        [("ticker", _REQUIRED), ("filing_url", _REQUIRED)],
    ),
    "compare_to_peers": (
        "modules.agents.skills.watchlist_skills", "compare_to_peers",
        [("ticker", _REQUIRED), ("peers", _REQUIRED)],
    ),
    "generate_thesis_statement": (
        "modules.agents.skills.watchlist_skills", "generate_thesis_statement",
        [("ticker", _REQUIRED), ("name", "")],
    ),
    # Portfolio skills
    "portfolio_scenario": (
        "modules.finance.portfolio_skills", "scenario",
        [("scenario_description", _REQUIRED)],
    ),
    "quarterly_portfolio_review": (
        "modules.finance.portfolio_skills", "quarterly_portfolio_review", [],
    ),
    "why_is_x_moving": (
        "modules.finance.portfolio_skills", "why_is_x_moving",
        [("ticker", _REQUIRED), ("context", "")],
    ),
    "rebalance_suggestor": (
        "modules.finance.portfolio_skills", "rebalance_suggestor",
        [("target_allocation", _REQUIRED)],
    ),
    "add_hypothesis": (
        "modules.finance.portfolio_skills", "add_hypothesis",
        [("ticker", _REQUIRED), ("hypothesis", _REQUIRED)],
    ),
    # Money skills
    "tax_scenario": (
        "modules.finance.money_skills", "tax_scenario",
        [("scenario_description", _REQUIRED), ("save_to_project", None)],
    ),
    "forecast_cash_flow": (
        "modules.finance.money_skills", "forecast_cash_flow",
        [("scenario_description", "")],
    ),
    "find_expense_optimizations": ("modules.finance.money_skills", "find_expense_optimizations", []),
    "quarterly_money_review": ("modules.finance.money_skills", "quarterly_money_review", []),
    "tax_deductible_review": ("modules.finance.money_skills", "tax_deductible_review", []),
    "bill_forecaster": ("modules.finance.money_skills", "bill_forecaster", []),
    # Project Q&A
    "ask_about_project": (
        "modules.agents.skills.ask_about_project", "ask",
        [("project_id", _REQUIRED), ("question", _REQUIRED)],
    ),
    "ask_anything": (
        "modules.agents.skills.ask_about_project", "ask_anything",
        [("question", _REQUIRED)],
    ),
}


# --- Home Skills & Agents directory (Item #4, Home_Redesign_Spec.md §3c) -----
# Curated directory entries. ``run_skill``: the SKILL_REGISTRY name to launch
# from the [run] button (None = not directly launchable here — ``run_target``
# routes to the page that owns the workflow, ``note`` explains a disabled row).
# ``patterns``: lowercase substrings matched against background run_ids
# ("<timestamp>_<label-with-underscores>") to find the latest run.
# ``cadence_days``: how often the skill should run; older than that = "due".
SKILL_DIRECTORY: list[dict] = [
    {
        "key": "market_researcher", "label": "Market Researcher",
        "run_skill": "market_researcher", "patterns": ("market_research",),
        "cadence_days": 7, "prompt_arg": None, "run_target": None, "note": None,
    },
    {
        "key": "earnings_reviewer", "label": "Earnings Reviewer",
        "run_skill": "earnings_reviewer", "patterns": ("earnings",),
        "cadence_days": None, "prompt_arg": "ticker", "run_target": None, "note": None,
    },
    {
        "key": "valuation_reviewer", "label": "Valuation Reviewer",
        "run_skill": None, "patterns": ("valuation",),
        "cadence_days": None, "prompt_arg": None,
        "run_target": "/workspace/portfolio", "note": "needs inputs — run from Portfolio workspace",
    },
    {
        "key": "idea_validator", "label": "Idea Validator",
        "run_skill": None, "patterns": ("stage_", "validate_"),
        "cadence_days": None, "prompt_arg": None,
        "run_target": "/ideas", "note": "run per-idea from the Ideas page",
    },
    {
        "key": "scenario_analyzer", "label": "Scenario Analyzer",
        "run_skill": "portfolio_scenario", "patterns": ("scenario",),
        "cadence_days": None, "prompt_arg": "scenario_description", "run_target": None, "note": None,
    },
    {
        "key": "monthly_wealth_check", "label": "Monthly Wealth Check",
        "run_skill": None, "patterns": ("wealth_check",),
        "cadence_days": 30, "prompt_arg": None,
        "run_target": None, "note": "skill not built yet (#77)",
    },
    {
        "key": "quarterly_portfolio_review", "label": "Quarterly Portfolio Review",
        "run_skill": "quarterly_portfolio_review", "patterns": ("quarterly_portfolio",),
        "cadence_days": 90, "prompt_arg": None, "run_target": None, "note": None,
    },
]


def _latest_runs_by_pattern() -> dict[str, dict]:
    """Newest background run per directory entry, matched by run_id substring."""
    latest: dict[str, dict] = {}
    if not BG_LOG_DIR.exists():
        return latest
    for f in sorted(BG_LOG_DIR.glob("*.status.json"), key=lambda p: p.name):
        run_id = f.name.removesuffix(".status.json")
        run_lower = run_id.lower()
        for entry in SKILL_DIRECTORY:
            if any(pat in run_lower for pat in entry["patterns"]):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                data["run_id"] = run_id
                # Filenames sort chronologically (timestamp prefix), so the
                # last assignment per key wins = the newest run.
                latest[entry["key"]] = data
    return latest


def _run_timestamp(run: dict) -> datetime | None:
    for field in ("completed_at", "failed_at", "started_at"):
        raw = run.get(field)
        if raw:
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                continue
    try:
        # Fall back to the run_id timestamp prefix: YYYYmmdd_HHMMSS.
        return datetime.strptime(run["run_id"][:15], "%Y%m%d_%H%M%S")
    except (KeyError, ValueError):
        return None


@router.get("/status")
def skills_status() -> dict:
    """The Skills & Agents directory with last-run + health per entry.

    Status legend (mirrors the Home spec): ``ok`` run recently / ``due`` cadence
    exceeded / ``failed`` last run errored / ``never`` no run on record.
    """
    runs = _latest_runs_by_pattern()
    now = datetime.now()
    out = []
    for entry in SKILL_DIRECTORY:
        run = runs.get(entry["key"])
        ts = _run_timestamp(run) if run else None
        if run is None:
            status = "never"
        elif run.get("status") == "failed":
            status = "failed"
        elif run.get("status") == "running":
            status = "ok"
        elif entry["cadence_days"] and ts and (now - ts).days > entry["cadence_days"]:
            status = "due"
        else:
            status = "ok"
        out.append({
            "key": entry["key"],
            "label": entry["label"],
            "status": status,
            "last_run_at": ts.isoformat() if ts else None,
            "last_run_id": run.get("run_id") if run else None,
            "last_run_status": run.get("status") if run else None,
            "run_skill": entry["run_skill"],
            "prompt_arg": entry["prompt_arg"],
            "run_target": entry["run_target"],
            "note": entry["note"],
        })
    return {"skills": out}


@router.get("")
def list_skills() -> dict:
    """List the registered skills and their accepted argument names."""
    out = {}
    for name, (module, callable_name, params) in SKILL_REGISTRY.items():
        out[name] = {
            "module": module,
            "callable": callable_name,
            "args": [{"name": p, "required": d is _REQUIRED} for p, d in params],
        }
    return {"skills": out}


@router.post("/{name}/run")
def run_skill(name: str, req: SkillRunRequest | None = None) -> dict:
    """Launch a registered skill in the background and return its run_id."""
    if name not in SKILL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown skill: {name}")
    module_path, callable_name, params = SKILL_REGISTRY[name]
    supplied = (req.args if req else {}) or {}

    positional: list = []
    for param_name, default in params:
        if param_name in supplied:
            positional.append(supplied[param_name])
        elif default is _REQUIRED:
            raise HTTPException(status_code=400, detail=f"Missing required arg: {param_name}")
        else:
            positional.append(default)

    label = (req.label if req and req.label else name)
    info = background.launch(
        module_path=module_path, callable_name=callable_name,
        args=positional, label=label,
    )
    return {"ok": True, "run_id": info["run_id"], "skill": name}
