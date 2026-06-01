"""Generic skill launcher — routes a skill name to its module/callable.

Every skill runs in the background (Phase 10a: skills are long ``claude -p``
calls). The endpoint returns a ``run_id`` immediately; poll ``GET /api/runs/{id}``
or subscribe to the run's WebSocket for progress.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import SkillRunRequest
from modules.agents import background

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
