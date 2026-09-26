"""Lump-sum deployment plans — the 50/30/20 tranche tracker (Chunk 6, item C6).

David deploys a lump sum in three tranches over ~10 weeks. A *plan* records the
intended schedule; tranches are marked executed as the trades actually happen.
Plans live in ``data/deployment_plans.jsonl`` (one JSON object per line, per-machine
personal data — gitignored like the ledger). The file is rewritten atomically
(tmp + replace) on every change; there are only ever a handful of plans.

Status: ``in_progress`` until every tranche is executed (then ``complete``, set
automatically), or ``cancelled`` by an explicit patch. Deleting removes the plan.
Executing a tranche only *records* it — it never touches the ledger; ``trade_id``
is an optional pointer back to the transaction David logged separately.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from core.config import DEPLOYMENT_PLANS_FILE, get_logger

logger = get_logger(__name__)

Status = Literal["in_progress", "complete", "cancelled"]
Bucket = Literal["etf_foundation", "single_stocks", "crypto", "wild_cards"]

DEFAULT_PCTS = (50.0, 30.0, 20.0)
DEFAULT_OFFSET_DAYS = (0, 28, 63)  # now, +4 weeks, +9 weeks
_PCT_TOLERANCE = 0.01


class PlanError(ValueError):
    """A request the plan rules reject (bad schedule, already executed, ...)."""


class NotFound(PlanError):
    """No plan with that id (or no tranche at that index)."""


class Tranche(BaseModel):
    pct: float
    target_date: date
    executed: bool = False
    amount_eur: Optional[float] = None
    trade_id: Optional[str] = None
    executed_date: Optional[date] = None


class Plan(BaseModel):
    id: str
    name: str
    total_eur: float
    target_bucket: Optional[Bucket] = None
    target_ticker: Optional[str] = None
    schedule: list[Tranche]
    created_at: date
    status: Status = "in_progress"

    @field_validator("target_ticker")
    @classmethod
    def _upper(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() or None if v else None


# --- storage ------------------------------------------------------------------------

def _read_all() -> list[Plan]:
    if not DEPLOYMENT_PLANS_FILE.exists():
        return []
    plans: list[Plan] = []
    for line in DEPLOYMENT_PLANS_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            plans.append(Plan(**json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:  # noqa: BLE001
            logger.warning("Skipping malformed deployment plan line: %s", exc)
    return plans


def _write_all(plans: list[Plan]) -> None:
    DEPLOYMENT_PLANS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEPLOYMENT_PLANS_FILE.with_suffix(DEPLOYMENT_PLANS_FILE.suffix + ".tmp")
    tmp.write_text("".join(p.model_dump_json() + "\n" for p in plans), encoding="utf-8")
    os.replace(tmp, DEPLOYMENT_PLANS_FILE)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "plan"


def _new_id(name: str, created: date, existing: set[str]) -> str:
    """``plan-2026-q1-etf-boost`` style id, de-duplicated with a numeric suffix."""
    base = f"plan-{created.year}-{_slug(name)}"
    pid, n = base, 2
    while pid in existing:
        pid, n = f"{base}-{n}", n + 1
    return pid


# --- validation ---------------------------------------------------------------------

def default_schedule(start: Optional[date] = None) -> list[Tranche]:
    """50/30/20 at start, +4 weeks and +9 weeks."""
    start = start or date.today()
    return [
        Tranche(pct=p, target_date=start + timedelta(days=d))
        for p, d in zip(DEFAULT_PCTS, DEFAULT_OFFSET_DAYS)
    ]


def _check_schedule(schedule: list[Tranche]) -> None:
    if not schedule:
        raise PlanError("a plan needs at least one tranche")
    if any(t.pct <= 0 for t in schedule):
        raise PlanError("every tranche percentage must be positive")
    total = sum(t.pct for t in schedule)
    if abs(total - 100.0) > _PCT_TOLERANCE:
        raise PlanError(f"tranche percentages must sum to 100 (got {total:g})")


def _check_target(bucket: Optional[str], ticker: Optional[str]) -> None:
    if bucket and ticker:
        raise PlanError("choose a target bucket or a target ticker, not both")


# --- CRUD ---------------------------------------------------------------------------

def create_plan(
    name: str,
    total_eur: float,
    target_bucket: Optional[str] = None,
    target_ticker: Optional[str] = None,
    schedule: Optional[list[dict]] = None,
    start: Optional[date] = None,
) -> Plan:
    """Create and store a plan (default 50/30/20 schedule when none is given)."""
    name = (name or "").strip()
    if not name:
        raise PlanError("a plan needs a name")
    if not total_eur or total_eur <= 0:
        raise PlanError("total_eur must be positive")
    _check_target(target_bucket, target_ticker)

    today = start or date.today()
    tranches = [Tranche(**t) for t in schedule] if schedule else default_schedule(today)
    _check_schedule(tranches)

    plans = _read_all()
    plan = Plan(
        id=_new_id(name, today, {p.id for p in plans}),
        name=name,
        total_eur=float(total_eur),
        target_bucket=target_bucket or None,
        target_ticker=target_ticker,
        schedule=tranches,
        created_at=today,
    )
    _write_all([*plans, plan])
    logger.info("Created deployment plan %s (%.0f EUR)", plan.id, plan.total_eur)
    return plan


def list_plans(status_filter: Optional[str] = None) -> list[Plan]:
    """All plans (creation order); ``status_filter`` keeps only that status."""
    plans = _read_all()
    return [p for p in plans if p.status == status_filter] if status_filter else plans


def get_plan(plan_id: str) -> Plan:
    for p in _read_all():
        if p.id == plan_id:
            return p
    raise NotFound(f"no deployment plan {plan_id!r}")


def _save(plan: Plan) -> Plan:
    plans = _read_all()
    _write_all([plan if p.id == plan.id else p for p in plans])
    return plan


def update_plan(plan_id: str, patch: dict[str, Any]) -> Plan:
    """Edit ``name`` / ``total_eur`` / target / ``status`` and pending tranches' dates.

    ``tranche_dates`` is ``{index: "YYYY-MM-DD"}``; an already-executed tranche's
    date is history and can't be changed. Only keys present in ``patch`` change,
    so ``{"target_ticker": None}`` clears the ticker.
    """
    plan = get_plan(plan_id)
    data = plan.model_dump()
    for key in ("name", "total_eur", "target_bucket", "target_ticker", "status"):
        if key in patch:
            data[key] = patch[key]
    if not str(data["name"]).strip():
        raise PlanError("a plan needs a name")
    if data["total_eur"] <= 0:
        raise PlanError("total_eur must be positive")
    _check_target(data["target_bucket"], data["target_ticker"])

    for idx, new_date in (patch.get("tranche_dates") or {}).items():
        i = int(idx)
        if not 0 <= i < len(data["schedule"]):
            raise NotFound(f"plan {plan_id!r} has no tranche {i}")
        if data["schedule"][i]["executed"]:
            raise PlanError(f"tranche {i} is already executed; its date can't change")
        data["schedule"][i]["target_date"] = new_date

    updated = Plan(**data)
    return _save(updated)


def mark_tranche_executed(
    plan_id: str,
    tranche_index: int,
    amount_eur: float,
    executed_date: Optional[date] = None,
    trade_id: Optional[str] = None,
) -> Plan:
    """Record that a tranche was deployed; completes the plan when none are pending."""
    plan = get_plan(plan_id)
    if plan.status == "cancelled":
        raise PlanError("this plan is cancelled")
    if not 0 <= tranche_index < len(plan.schedule):
        raise NotFound(f"plan {plan_id!r} has no tranche {tranche_index}")
    tranche = plan.schedule[tranche_index]
    if tranche.executed:
        raise PlanError(f"tranche {tranche_index} is already executed")
    if amount_eur is None or amount_eur <= 0:
        raise PlanError("amount_eur must be positive")

    tranche.executed = True
    tranche.amount_eur = float(amount_eur)
    tranche.executed_date = executed_date or date.today()
    tranche.trade_id = (trade_id or "").strip() or None
    if all(t.executed for t in plan.schedule):
        plan.status = "complete"
    return _save(plan)


def delete_plan(plan_id: str) -> None:
    plans = _read_all()
    if not any(p.id == plan_id for p in plans):
        raise NotFound(f"no deployment plan {plan_id!r}")
    _write_all([p for p in plans if p.id != plan_id])


# --- dashboard summary --------------------------------------------------------------

def plan_progress(plan: Plan, today: Optional[date] = None) -> dict:
    """Deployed %, EUR, and the next pending tranche (with days until it's due).

    ``days_until`` is negative when the tranche is overdue. The next tranche is the
    pending one with the earliest target date.
    """
    today = today or date.today()
    done = [t for t in plan.schedule if t.executed]
    pending = sorted(
        ((i, t) for i, t in enumerate(plan.schedule) if not t.executed),
        key=lambda it: (it[1].target_date, it[0]),
    )
    nxt = None
    if pending and plan.status == "in_progress":
        i, t = pending[0]
        nxt = {"index": i, "pct": t.pct, "target_date": t.target_date.isoformat(),
               "days_until": (t.target_date - today).days}
    return {
        "deployed_pct": sum(t.pct for t in done),
        "deployed_eur": sum(t.amount_eur or 0.0 for t in done),
        "planned_eur": plan.total_eur,
        "executed_count": len(done),
        "tranche_count": len(plan.schedule),
        "next_tranche": nxt,
    }


def progress_summary(plans: list[Plan], today: Optional[date] = None) -> dict:
    """Dashboard roll-up over ``plans``: active count and the soonest tranche due."""
    today = today or date.today()
    active = [p for p in plans if p.status == "in_progress"]
    dues = []
    for p in active:
        nxt = plan_progress(p, today)["next_tranche"]
        if nxt:
            dues.append({"plan_id": p.id, "plan_name": p.name, **nxt})
    dues.sort(key=lambda d: d["days_until"])
    return {"active_count": len(active), "total_count": len(plans), "next_due": dues[0] if dues else None}


def with_progress(plan: Plan, today: Optional[date] = None) -> dict:
    """A plan as JSON-ready dict plus its ``progress`` block."""
    return {**json.loads(plan.model_dump_json()), "progress": plan_progress(plan, today)}
