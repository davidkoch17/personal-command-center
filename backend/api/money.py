"""Money API — wraps modules.finance.money + tax-scenario skill."""
from __future__ import annotations

import json

from fastapi import APIRouter, Query

from backend.api._helpers import df_records, clean_dict
from backend.models.schemas import ContributionOverrideRequest, TaxScenarioRequest
from core.config import DATA_DIR, get_logger
from modules.finance import money, networth_history, tr_contributions
from modules.agents import background

logger = get_logger(__name__)

router = APIRouter()

MONEY_SKILLS_MODULE = "modules.finance.money_skills"

# Per-machine wealth reference data (insurance · PKV · accounts) — edited by hand
# in data/wealth_config.json; gitignored. The endpoint serves the default
# template (structure only, no invented figures) merged with any saved overrides.
WEALTH_CONFIG_FILE = DATA_DIR / "wealth_config.json"


@router.get("/snapshot")
def snapshot() -> dict:
    """Cash balance, net worth (with breakdown), monthly burn, and runway.

    ``net_worth`` here is the app-wide authoritative figure (Excel-sourced,
    via ``money.latest_net_worth()``) — every "net worth" headline in the UI
    must read from this field, not from the live-ledger-priced
    ``/api/finance/networth/*`` endpoints (chart/analytics only; see
    ``modules.finance.period_pnl``'s docstring for why the two can diverge).
    """
    cash = money.current_cash_balance()
    nw = clean_dict(money.latest_net_worth())
    burn = money.monthly_fixed_estimate()
    # N1 — record a monthly net-worth snapshot on each finance refresh (deduped
    # per month). Wrapped so a store failure can never break the snapshot call.
    try:
        networth_history.record_snapshot(
            nw.get("total"),
            components={
                "bank": nw.get("bank"),
                "tr": nw.get("tr"),
                "crypto": nw.get("crypto"),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("net-worth snapshot record failed: %s", exc)
    return {
        "cash_balance": cash,
        "net_worth": nw.get("total"),
        "net_worth_breakdown": nw,
        "monthly_burn": burn,
        "runway_months": money.runway_months(cash, burn),
    }


@router.get("/networth-history")
def networth_history_endpoint() -> dict:
    """Monthly net-worth trend (N1) — sheet history overlaid with live snapshots."""
    series = networth_history.history()
    latest = series[-1] if series else None
    first = series[0] if series else None
    change = (
        round(latest["total"] - first["total"], 2)
        if latest and first and latest["total"] is not None and first["total"] is not None
        else None
    )
    return {"history": series, "count": len(series), "latest": latest, "change_since_start": change}


@router.get("/available-months")
def available_months() -> dict:
    """Months that have transaction data, sorted ascending."""
    return {"months": money.available_months()}


@router.get("/report/{month}")
def monthly_report(month: str) -> dict:
    """Full P&L for one month: income breakdown, expenses by category, transaction list."""
    income = money.monthly_income(month)
    by_cat = money.monthly_expenses_by_category(month)
    total_exp = round(sum(c["amount"] for c in by_cat), 2)
    net = round(income["total"] - total_exp, 2)
    rate = round(net / income["total"], 4) if income["total"] else None
    return {
        "month": month,
        "income": income,
        "expenses": {"by_category": by_cat, "total": total_exp},
        "net": net,
        "savings_rate": rate,
        "transactions": money.monthly_transactions(month),
    }


@router.get("/allocation/{month}")
def allocation(month: str) -> dict:
    """Income-by-type, expenses, investable surplus, savings rate, reserve status,
    the recommended reserve/invest split, and — dependent on the TR statement
    parser being verified (see ``tr_contributions`` module docstring) — the
    actual TR contribution for the month vs. that recommendation."""
    by_cat = money.monthly_expenses_by_category(month)
    total_exp = round(sum(c["amount"] for c in by_cat), 2)
    split = money.split_recommendation(month)
    contribution = tr_contributions.monthly_contribution(month)
    contribution_vs_recommended = (
        round(contribution["value"] - split["to_invest"], 2)
        if contribution["value"] is not None else None
    )
    return {
        "month": month,
        "income_by_type": money.monthly_income_by_type(month),
        "investable_income": money.investable_income(month),
        "expenses": {"by_category": by_cat, "total": total_exp},
        "investable_surplus": split["surplus"],
        "savings_rate": split["savings_rate"],
        "reserve": split["reserve"],
        "split_recommendation": {
            "to_reserve": split["to_reserve"],
            "to_invest": split["to_invest"],
        },
        # actual_contribution.value is None (with .flags explaining why) when TR
        # data for the month is missing/unreliable — see tr_contributions.py.
        # Positive vs_recommended = invested more than recommended; negative = less.
        "actual_contribution": contribution,
        "contribution_vs_recommended": contribution_vs_recommended,
    }


@router.post("/allocation/{month}/contribution-override")
def set_contribution_override(month: str, override: ContributionOverrideRequest) -> dict:
    """Manually set (or, with ``value: null``, clear) a month's TR contribution.

    For months ``monthly_contribution()`` flags unreliable (missing/estimate-
    flagged TR snapshots, stale post-close pricing, etc.) — David enters the
    real figure by hand instead of trusting a guess.
    """
    tr_contributions.set_override(month, override.value)
    return {"ok": True, "month": month, "value": override.value}


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


# --- Wealth reference: insurance · PKV decline · Mehrkontenmodell -----------
# Structure only (no invented premiums/balances). David fills the detail fields
# in data/wealth_config.json; the third insurance type stays a marked placeholder
# until he resolves it (Haftpflicht / Unfall / Hausrat — open decision in the
# v2 spec). Each entry's `status` of "placeholder" tells the UI to render an
# explicit "to record" state rather than a fabricated value.
_WEALTH_CONFIG_DEFAULT: dict = {
    "insurance": [
        {
            "key": "kv",
            "type": "Krankenversicherung (KV)",
            "status": "placeholder",
            "provider": None,
            "monthly_eur": None,
            "notes": "GKV vs. PKV — record the chosen policy here.",
        },
        {
            "key": "bu",
            "type": "Berufsunfähigkeitsversicherung (BU)",
            "status": "placeholder",
            "provider": None,
            "monthly_eur": None,
            "notes": "High priority before Evercore start — record provider + monthly premium.",
        },
        {
            "key": "third",
            "type": "Third insurance — TBD",
            "status": "placeholder",
            "provider": None,
            "monthly_eur": None,
            "notes": "Open decision: Haftpflicht / Unfall / Hausrat. Pick one, then record it.",
        },
    ],
    # PKV decline record — the spec asks this be visible. Outcome unknown to the
    # dashboard; left as a marked record for David to confirm.
    "pkv_decision": {
        "status": "unrecorded",
        "decided_on": None,
        "outcome": None,
        "rationale": None,
        "notes": "PKV decision (memo: weighed late May 2026). Record outcome + rationale here.",
    },
    # Mehrkontenmodell — account *purposes* are the framework (not personal data);
    # bank + balance fields stay empty until recorded.
    "accounts": [
        {"key": "giro", "label": "Girokonto (running costs)", "bank": None, "purpose": "Fixed + daily spend"},
        {"key": "tagesgeld", "label": "Tagesgeld (Notgroschen)", "bank": None, "purpose": "Emergency buffer → €4,000 (Phase 1)"},
        {"key": "depot", "label": "Depot (Trade Republic)", "bank": None, "purpose": "Investing (Phase 2 funding target)"},
        {"key": "spending", "label": "Spending / lifestyle", "bank": None, "purpose": "Discretionary, ring-fenced"},
    ],
}


@router.get("/wealth-config")
def wealth_config() -> dict:
    """Insurance tracker + PKV record + account structure (Mehrkontenmodell).

    Serves the default structural template merged with any per-machine overrides
    saved in ``data/wealth_config.json``. No figures are invented — empty fields
    render as explicit "to record" states in the UI.
    """
    config = json.loads(json.dumps(_WEALTH_CONFIG_DEFAULT))  # deep copy
    if WEALTH_CONFIG_FILE.exists():
        try:
            override = json.loads(WEALTH_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(override, dict):
                config.update(override)
        except (json.JSONDecodeError, OSError) as exc:  # noqa: BLE001
            logger.warning("wealth_config.json unreadable (%s); serving default", exc)
    config["source"] = "wealth_config.json" if WEALTH_CONFIG_FILE.exists() else "default-template"
    return config


@router.post("/tax-scenario")
def tax_scenario(req: TaxScenarioRequest) -> dict:
    """Run the German tax-scenario skill in the background (writes a dated MD file)."""
    info = background.launch(
        module_path=MONEY_SKILLS_MODULE, callable_name="tax_scenario",
        args=[req.scenario_description, req.save_to_project], label="Tax scenario",
    )
    return {"ok": True, "run_id": info["run_id"]}
