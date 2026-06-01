"""Money API — wraps modules.finance.money + tax-scenario skill."""
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.api._helpers import df_records, clean_dict
from backend.models.schemas import TaxScenarioRequest
from modules.finance import money
from modules.agents import background

router = APIRouter()

MONEY_SKILLS_MODULE = "modules.finance.money_skills"


@router.get("/snapshot")
def snapshot() -> dict:
    """Cash balance, net worth (with breakdown), monthly burn, and runway."""
    cash = money.current_cash_balance()
    nw = clean_dict(money.latest_net_worth())
    burn = money.monthly_fixed_estimate()
    return {
        "cash_balance": cash,
        "net_worth": nw.get("total"),
        "net_worth_breakdown": nw,
        "monthly_burn": burn,
        "runway_months": money.runway_months(cash, burn),
    }


@router.get("/cashflow")
def cashflow(months: int = Query(12, ge=1)) -> dict:
    """Income / expenses / savings per month (most recent ``months``)."""
    records = df_records(money.monthly_totals())
    return {"months": months, "cashflow": records[-months:]}


@router.get("/categories")
def categories(months: int = Query(6, ge=1)) -> dict:
    """Monthly spending broken down by category (most recent ``months``)."""
    pivot = money.monthly_spending_by_category()
    if pivot is None or pivot.empty:
        return {"months": months, "categories": []}
    records = df_records(pivot.reset_index())
    return {"months": months, "categories": records[-months:]}


@router.post("/tax-scenario")
def tax_scenario(req: TaxScenarioRequest) -> dict:
    """Run the German tax-scenario skill in the background (writes a dated MD file)."""
    info = background.launch(
        module_path=MONEY_SKILLS_MODULE, callable_name="tax_scenario",
        args=[req.scenario_description, req.save_to_project], label="Tax scenario",
    )
    return {"ok": True, "run_id": info["run_id"]}
