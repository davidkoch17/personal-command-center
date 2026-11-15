"""Lebensplan API — interactive front for ``Traumleben_Plan.xlsx``.

The Excel holds the base inputs; the playground sends overrides (partial
inputs) and gets the recomputed plan back. Scenarios are saved as overrides
relative to the base; "promote" writes inputs back into the Excel.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from core.config import LIFEPLAN_SCENARIOS, LIFEPLAN_XLSX, get_logger
from modules.finance import networth_history
from modules.lifeplan import excel_writer, scenarios
from modules.lifeplan.inputs import (
    LifePlanInputs,
    apply_overrides,
    deep_merge,
    diff,
    effective_inputs,
    read_inputs,
)
from modules.lifeplan.model import compute

logger = get_logger(__name__)

router = APIRouter()


class ComputeRequest(BaseModel):
    overrides: dict[str, Any] = {}


class ScenarioRequest(BaseModel):
    name: str
    inputs: dict[str, Any]          # full input set from the playground
    id: Optional[str] = None        # set → overwrite this scenario


class PromoteRequest(BaseModel):
    inputs: dict[str, Any]


# --------------------------------------------------------------------------- helpers
def live_wealth() -> dict[str, Any] | None:
    """Latest net-worth snapshot (``total`` + date), or None."""
    records = [r for r in networth_history._load() if r.get("total") is not None]
    if not records:
        return None
    last = max(records, key=lambda r: str(r.get("date") or r.get("month") or ""))
    return {"total": float(last["total"]), "date": last.get("date") or last.get("month"),
            "components": last.get("components")}


def _base() -> LifePlanInputs:
    if not LIFEPLAN_XLSX.exists():
        raise HTTPException(status_code=404, detail=f"Excel nicht gefunden: {LIFEPLAN_XLSX}")
    try:
        return read_inputs(LIFEPLAN_XLSX)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail="Excel ist gesperrt") from exc


def _run(inputs: LifePlanInputs, live: dict[str, Any] | None) -> dict[str, Any]:
    eff = effective_inputs(inputs, live["total"] if live else None)
    return compute(eff).to_dict()


def _merge(base: LifePlanInputs, overrides: dict[str, Any]) -> LifePlanInputs:
    try:
        return apply_overrides(base, overrides)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc


def _scenario_view(base: LifePlanInputs, s: dict[str, Any]) -> dict[str, Any]:
    merged = deep_merge(base.model_dump(), s.get("overrides") or {})
    return {**s, "inputs": LifePlanInputs.model_validate(merged).model_dump()}


# --------------------------------------------------------------------------- routes
@router.get("")
def get_lifeplan() -> dict[str, Any]:
    """Base inputs (from Excel) + computed plan + live net worth."""
    base = _base()
    live = live_wealth()
    return {
        "inputs": base.model_dump(),
        "result": _run(base, live),
        "live_wealth": live,
        "excel_path": str(LIFEPLAN_XLSX),
    }


@router.post("/compute")
def compute_plan(req: ComputeRequest) -> dict[str, Any]:
    """Base + overrides → plan. Overrides may be partial or a full input set."""
    inputs = _merge(_base(), req.overrides)
    return {"inputs": inputs.model_dump(), "result": _run(inputs, live_wealth())}


@router.get("/scenarios")
def get_scenarios() -> dict[str, Any]:
    base = _base()
    return {"scenarios": [_scenario_view(base, s) for s in scenarios.list_scenarios(LIFEPLAN_SCENARIOS)]}


@router.post("/scenarios")
def save_scenario(req: ScenarioRequest) -> dict[str, Any]:
    """Save the playground state as a named scenario (stored as overrides)."""
    base = _base()
    full = _merge(base, req.inputs)
    overrides = diff(base.model_dump(), full.model_dump())
    try:
        saved = scenarios.save_scenario(LIFEPLAN_SCENARIOS, req.name, overrides, req.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Szenario unbekannt: {req.id}") from exc
    return _scenario_view(base, saved)


@router.delete("/scenarios/{scenario_id}")
def delete_scenario(scenario_id: str) -> dict[str, Any]:
    try:
        scenarios.delete_scenario(LIFEPLAN_SCENARIOS, scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Szenario unbekannt: {scenario_id}") from exc
    return {"ok": True}


@router.post("/promote")
def promote(req: PromoteRequest) -> dict[str, Any]:
    """Write the playground inputs into the Excel as the new base (with backup)."""
    base = _base()
    live = live_wealth()
    inputs = effective_inputs(_merge(base, req.inputs), live["total"] if live else None)
    try:
        info = excel_writer.write_inputs(LIFEPLAN_XLSX, inputs)
    except excel_writer.ExcelLockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    new_base = read_inputs(LIFEPLAN_XLSX)
    return {**info, "inputs": new_base.model_dump(), "result": _run(new_base, live)}


@router.post("/open-excel")
def open_excel() -> dict[str, Any]:
    """Open the workbook in Excel on David's machine."""
    if not LIFEPLAN_XLSX.exists():
        raise HTTPException(status_code=404, detail=f"Excel nicht gefunden: {LIFEPLAN_XLSX}")
    try:
        os.startfile(str(LIFEPLAN_XLSX))  # noqa: S606 - local-only server
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Konnte Excel nicht öffnen: {exc}") from exc
    return {"ok": True, "opened": str(LIFEPLAN_XLSX)}
