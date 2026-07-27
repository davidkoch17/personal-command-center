"""Cash Flow pillar API — wraps modules.finance.cashflow (the ledger-backed
income/expense tracker). Independent of money.py's Excel-sourced net-worth/
investing endpoints; the two domains stay deliberately separate."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.models.schemas import (
    CashflowBudgetRequest,
    CashflowGoalRequest,
    CashflowResolveRequest,
    ReserveBalanceRequest,
)
from core.config import CASHFLOW_EXPENSE_CATEGORIES, CASHFLOW_INCOME_CATEGORIES, get_logger
from modules.finance import cashflow, tr_contributions

logger = get_logger(__name__)

router = APIRouter()


@router.get("/categories")
def categories() -> dict:
    """Canonical expense/income category taxonomy (for dropdowns + chart colors)."""
    return {"expense_categories": CASHFLOW_EXPENSE_CATEGORIES, "income_categories": CASHFLOW_INCOME_CATEGORIES}


@router.get("/months")
def months() -> dict:
    """Months that have at least one ledger entry, sorted ascending."""
    return {"months": cashflow.available_months()}


@router.get("/summary/{month}")
def summary(month: str) -> dict:
    """Income/expense breakdown, net, savings rate, and goal progress for one month."""
    s = cashflow.monthly_summary(month)
    s["goal"] = cashflow.goal_progress(month)
    return s


@router.get("/trend")
def trend(months: int = Query(12, ge=1)) -> dict:
    """Income / expenses / savings per month (most recent ``months``)."""
    return {"months": months, "trend": cashflow.trend(months)}


@router.get("/category-trend")
def category_trend(months: int = Query(12, ge=1)) -> dict:
    """Monthly expense totals by category (most recent ``months``)."""
    return {"months": months, "categories": cashflow.category_trend(months)}


@router.get("/transactions/{month}")
def transactions(month: str) -> dict:
    """Every ledger entry for one month, sorted by date."""
    return {"month": month, "transactions": cashflow.monthly_transactions(month)}


@router.get("/reserve/{month}")
def reserve(month: str) -> dict:
    """Reserve status, recommended reserve/invest split, and actual TR contribution
    vs. that recommendation — the Reserve & Allocation tab's data source."""
    split = cashflow.split_recommendation(month)
    contribution = tr_contributions.monthly_contribution(month)
    contribution_vs_recommended = (
        round(contribution["value"] - split["to_invest"], 2)
        if contribution["value"] is not None else None
    )
    return {
        "month": month,
        "investable_income": cashflow.investable_income(month),
        "investable_surplus": split["surplus"],
        "savings_rate": split["savings_rate"],
        "reserve": split["reserve"],
        "split_recommendation": {"to_reserve": split["to_reserve"], "to_invest": split["to_invest"]},
        "actual_contribution": contribution,
        "contribution_vs_recommended": contribution_vs_recommended,
    }


@router.post("/reserve/{month}/balance")
def set_reserve_balance(month: str, req: ReserveBalanceRequest) -> dict:
    """Manually record the Notgroschen reserve account balance for ``month``
    (no automated bank feed yet — David reports the figure by hand)."""
    cashflow.set_reserve_balance(month, req.value)
    return {"ok": True, "month": month, "value": req.value}


@router.get("/goal")
def get_goal() -> dict:
    return {"monthly_savings_goal": cashflow.get_savings_goal()}


@router.post("/goal")
def set_goal(req: CashflowGoalRequest) -> dict:
    """Set (or, with ``value: null``, clear) the monthly savings-goal target."""
    cashflow.set_savings_goal(req.value)
    return {"ok": True, "monthly_savings_goal": req.value}


@router.get("/needs-review")
def needs_review() -> dict:
    """Ledger entries currently flagged for review (question + full row), for
    the in-app needs-review queue that replaces the ad-hoc questions doc."""
    rows = cashflow.needs_review_entries()
    return {
        "entries": [{**e.model_dump(), "date": e.date.isoformat()} for e in rows],
        "count": len(rows),
    }


@router.post("/needs-review/{id}/resolve")
def resolve_needs_review(id: str, req: CashflowResolveRequest) -> dict:
    """Apply David's answer to one flagged entry and clear its review flag."""
    fields = req.model_dump(exclude_unset=True)
    updated = cashflow.resolve_entry(id, **fields)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Cashflow entry {id} not found")
    return {"ok": True, "entry": {**updated.model_dump(), "date": updated.date.isoformat()}}


@router.get("/budget")
def get_budget() -> dict:
    return {"budget": cashflow.get_budget()}


@router.post("/budget")
def set_budget(req: CashflowBudgetRequest) -> dict:
    """Set (or, with ``value: null``, clear) one category's budget target."""
    cashflow.set_budget_target(req.category, req.value)
    return {"ok": True, "budget": cashflow.get_budget()}
