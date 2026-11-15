"""Typed Lebensplan inputs and the mapping to the Excel input cells.

The Excel (``Traumleben_Plan.xlsx``) is the source of the *base* assumptions.
``CELL_MAP`` is the single mapping between an input field and its cell; the
reader (here) and the writer (``excel_writer``) both use it, so the two can
never drift apart.

Fields that have no cell in the Excel (``bonus_factor``, ``md_age``,
``wealth_source``) are playground controls. They are folded into the plain
values by :func:`effective_inputs` before computing or writing back.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from core.config import get_logger

logger = get_logger(__name__)

# The Cape Town house is priced in Rand in the Excel (``=20000000/FX``); the Rand
# price itself is a constant inside that formula, not an input cell.
CAPE_HOUSE_ZAR = 20_000_000.0

DEFAULT_CAREER_PATH = "banking"


# --------------------------------------------------------------------------- models
class StartInputs(BaseModel):
    birth_year: int = 2001
    start_year: int = 2027
    start_wealth: float = 10_000
    # "manual" = the value above; "dashboard" = latest net-worth snapshot.
    wealth_source: Literal["manual", "dashboard"] = "manual"


class CareerStage(BaseModel):
    name: str
    age: float
    fix: float
    bonus: float


class CareerInputs(BaseModel):
    # Several career paths can live side by side later (PE with carry,
    # founder …); v1 only has "banking", which maps to the Excel table.
    path: str = DEFAULT_CAREER_PATH
    paths: dict[str, list[CareerStage]] = Field(default_factory=dict)
    work_until_age: float = 55
    bonus_factor: float = 1.0           # quick slider, 0.5–1.5
    md_age: Optional[float] = None      # quick slider; None = as in the table


class SpendingBand(BaseModel):
    age: float
    pct: float


class SpendingInputs(BaseModel):
    bands: list[SpendingBand] = Field(default_factory=list)


class FamilyInputs(BaseModel):
    marriage_age: float = 31
    partner_gross: float = 0
    child1_age: float = 32
    child2_age: float = 34   # 999 = no second child


class MilestoneAges(BaseModel):
    """Purchase age per milestone; 999 = never buy."""
    main_car: float = 28
    fun_car: float = 30
    house_munich: float = 36
    sports_car: float = 38
    house_cape: float = 45


class Assumptions(BaseModel):
    fx_eur_zar: float = 18.4
    de_transfer_tax: float = 0.035
    de_notary: float = 0.02
    de_broker: float = 0.0357
    za_transfer_duty: float = 0.11
    za_legal: float = 0.015
    living_today: float = 2500
    reserve_months: float = 6
    mortgage_rate: float = 0.042
    amortization: float = 0.02
    ltv: float = 0.8
    za_equity_share: float = 1
    net_ratio: float = 0.55
    upkeep_main_car: float = 600
    upkeep_sports_car: float = 900
    upkeep_fun_car: float = 250
    travel_before_cape: float = 2500
    withdrawal_rate: float = 0.035
    withdrawal_tax: float = 0.2
    depr_main_car: float = 0.12
    depr_sports_car: float = 0.07
    depr_fun_car: float = 0
    partner_net_monthly: float = 0
    return_liquid: float = 0.04
    werbungskosten: float = 1230
    health_deductible: float = 8000
    bbg: float = 101_400
    pension_rate: float = 0.093
    unemployment_rate: float = 0.013
    soli_threshold: float = 20_350
    church_tax: float = 0
    employer_pkv: float = 600
    pkv_self: float = 892.75
    pkv_partner: float = 600
    pkv_child: float = 200
    bu_insurance: float = 100
    rent_today: float = 1000
    rent_family: float = 3500
    min_living: float = 1500
    child_0_5: float = 1000
    child_6_18: float = 2300
    child_19_24: float = 1000


class PriceRange(BaseModel):
    low: float
    high: float
    price: float


class CarPrice(PriceRange):
    fees_pct: float = 0


class OneOffInputs(BaseModel):
    house_munich: PriceRange = PriceRange(low=2_500_000, high=3_700_000, price=3_000_000)
    main_car: CarPrice = CarPrice(low=48_000, high=100_000, price=85_000)
    sports_car: CarPrice = CarPrice(low=100_000, high=230_000, price=180_000)
    fun_car: CarPrice = CarPrice(low=20_000, high=120_000, price=70_000)


class RunningCosts(BaseModel):
    """Laufende Kosten, € per month (net)."""
    house_munich: float = 2000
    house_cape: float = 1700
    household_help: float = 1500
    cars: float = 1750
    groceries: float = 1500
    dining: float = 1000
    kids: float = 4600
    travel: float = 3500
    leisure: float = 1500
    insurance: float = 2200
    misc: float = 800
    buffer: float = 0.1


class LifePlanInputs(BaseModel):
    start: StartInputs = StartInputs()
    career: CareerInputs = CareerInputs()
    spending: SpendingInputs = SpendingInputs()
    family: FamilyInputs = FamilyInputs()
    milestones: MilestoneAges = MilestoneAges()
    assumptions: Assumptions = Assumptions()
    one_off: OneOffInputs = OneOffInputs()
    running: RunningCosts = RunningCosts()


# --------------------------------------------------------------------------- mapping
# (sheet, cell, path) — path walks the dict form of LifePlanInputs.
Path_ = tuple[Any, ...]
KD, AN, TE, LK = "Key Drivers", "Annahmen", "Traumleben Einmalig", "Laufende Kosten"

CAREER_FIRST_ROW, CAREER_LAST_ROW = 11, 24      # Key Drivers B11:E24
BAND_FIRST_ROW, BAND_LAST_ROW = 30, 33          # Key Drivers B30:C33


def _build_cell_map() -> list[tuple[str, str, Path_]]:
    cells: list[tuple[str, str, Path_]] = [
        (KD, "C5", ("start", "birth_year")),
        (KD, "C6", ("start", "start_year")),
        (KD, "C7", ("start", "start_wealth")),
        (KD, "C26", ("career", "work_until_age")),
        (KD, "C38", ("family", "marriage_age")),
        (KD, "C39", ("family", "partner_gross")),
        (KD, "C40", ("family", "child1_age")),
        (KD, "C41", ("family", "child2_age")),
        (KD, "C44", ("milestones", "main_car")),
        (KD, "C45", ("milestones", "fun_car")),
        (KD, "C46", ("milestones", "house_munich")),
        (KD, "C47", ("milestones", "sports_car")),
        (KD, "C48", ("milestones", "house_cape")),
    ]
    for i, row in enumerate(range(CAREER_FIRST_ROW, CAREER_LAST_ROW + 1)):
        base = ("career", "paths", DEFAULT_CAREER_PATH, i)
        cells += [
            (KD, f"C{row}", base + ("age",)),
            (KD, f"D{row}", base + ("fix",)),
            (KD, f"E{row}", base + ("bonus",)),
        ]
    for i, row in enumerate(range(BAND_FIRST_ROW, BAND_LAST_ROW + 1)):
        cells += [
            (KD, f"B{row}", ("spending", "bands", i, "age")),
            (KD, f"C{row}", ("spending", "bands", i, "pct")),
        ]
    annahmen = [
        ("B5", "fx_eur_zar"), ("B6", "de_transfer_tax"), ("B7", "de_notary"),
        ("B8", "de_broker"), ("B9", "za_transfer_duty"), ("B10", "za_legal"),
        ("B11", "living_today"), ("B12", "reserve_months"), ("B13", "mortgage_rate"),
        ("B14", "amortization"), ("B15", "ltv"), ("B16", "za_equity_share"),
        ("B17", "net_ratio"), ("B18", "upkeep_main_car"), ("B19", "upkeep_sports_car"),
        ("B20", "upkeep_fun_car"), ("B21", "travel_before_cape"), ("B22", "withdrawal_rate"),
        ("B23", "withdrawal_tax"), ("B24", "depr_main_car"), ("B25", "depr_sports_car"),
        ("B26", "depr_fun_car"), ("B27", "partner_net_monthly"), ("B30", "return_liquid"),
        ("B31", "werbungskosten"), ("B32", "health_deductible"), ("B33", "bbg"),
        ("B34", "pension_rate"), ("B35", "unemployment_rate"), ("B36", "soli_threshold"),
        ("B37", "church_tax"), ("B38", "employer_pkv"), ("B39", "pkv_self"),
        ("B40", "pkv_partner"), ("B41", "pkv_child"), ("B42", "bu_insurance"),
        ("B43", "rent_today"), ("B44", "rent_family"), ("B45", "min_living"),
        ("B46", "child_0_5"), ("B47", "child_6_18"), ("B48", "child_19_24"),
    ]
    cells += [(AN, cell, ("assumptions", key)) for cell, key in annahmen]
    cells += [
        (TE, "C5", ("one_off", "house_munich", "low")),
        (TE, "D5", ("one_off", "house_munich", "high")),
        (TE, "E5", ("one_off", "house_munich", "price")),
    ]
    for row, key in ((7, "main_car"), (8, "sports_car"), (9, "fun_car")):
        cells += [
            (TE, f"C{row}", ("one_off", key, "low")),
            (TE, f"D{row}", ("one_off", key, "high")),
            (TE, f"E{row}", ("one_off", key, "price")),
            (TE, f"F{row}", ("one_off", key, "fees_pct")),
        ]
    running = [
        ("C5", "house_munich"), ("C6", "house_cape"), ("C7", "household_help"),
        ("C8", "cars"), ("C9", "groceries"), ("C10", "dining"), ("C11", "kids"),
        ("C12", "travel"), ("C13", "leisure"), ("C14", "insurance"), ("C15", "misc"),
        ("F16", "buffer"),
    ]
    cells += [(LK, cell, ("running", key)) for cell, key in running]
    return cells


CELL_MAP: list[tuple[str, str, Path_]] = _build_cell_map()


# --------------------------------------------------------------------------- dict helpers
def get_path(data: Any, path: Path_) -> Any:
    """Walk ``path`` through nested dicts/lists."""
    for key in path:
        data = data[key]
    return data


def set_path(data: Any, path: Path_, value: Any) -> None:
    """Set ``value`` at ``path``, creating dicts/list slots on the way."""
    for i, key in enumerate(path[:-1]):
        nxt = path[i + 1]
        if isinstance(data, list):
            while len(data) <= key:
                data.append({})
            data = data[key]
        else:
            data = data.setdefault(key, [] if isinstance(nxt, int) else {})
    last = path[-1]
    if isinstance(data, list):
        while len(data) <= last:
            data.append(None)
    data[last] = value


def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Return ``base`` with ``overrides`` merged in (dicts recurse, lists replace)."""
    out = copy.deepcopy(base)
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def diff(base: dict[str, Any], full: dict[str, Any]) -> dict[str, Any]:
    """Minimal overrides so that ``deep_merge(base, result) == full``."""
    out: dict[str, Any] = {}
    for key, value in full.items():
        if key not in base:
            out[key] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(base[key], dict):
            sub = diff(base[key], value)
            if sub:
                out[key] = sub
        elif value != base[key]:
            out[key] = copy.deepcopy(value)
    return out


def apply_overrides(base: LifePlanInputs, overrides: dict[str, Any] | None) -> LifePlanInputs:
    """Validate ``base`` + partial ``overrides`` into a full input set."""
    return LifePlanInputs.model_validate(deep_merge(base.model_dump(), overrides or {}))


# --------------------------------------------------------------------------- read
def read_inputs(xlsx: Path) -> LifePlanInputs:
    """Read every input cell of the Excel into ``LifePlanInputs``."""
    import openpyxl

    wb = openpyxl.load_workbook(xlsx, read_only=True)
    try:
        data: dict[str, Any] = {}
        for sheet, cell, path in CELL_MAP:
            value = wb[sheet][cell].value
            set_path(data, path, 0 if value is None else value)
        stages = data["career"]["paths"][DEFAULT_CAREER_PATH]
        ws = wb[KD]
        for i, row in enumerate(range(CAREER_FIRST_ROW, CAREER_LAST_ROW + 1)):
            stages[i]["name"] = str(ws[f"B{row}"].value or f"Stufe {i + 1}")
    finally:
        wb.close()
    logger.debug("lifeplan inputs read from %s", xlsx)
    return LifePlanInputs.model_validate(data)


def to_cells(inputs: LifePlanInputs) -> list[tuple[str, str, Any]]:
    """(sheet, cell, value) for every mapped input — the writer's payload."""
    data = inputs.model_dump()
    return [(sheet, cell, get_path(data, path)) for sheet, cell, path in CELL_MAP]


# --------------------------------------------------------------------------- effective
def active_stages(inputs: LifePlanInputs) -> list[CareerStage]:
    """Career table of the selected path (empty list if unknown)."""
    return inputs.career.paths.get(inputs.career.path, [])


def effective_stages(inputs: LifePlanInputs) -> list[CareerStage]:
    """Apply the quick sliders (bonus factor, MD age) to the career table.

    The MD slider moves every stage from the first "Director" onwards by the
    same number of years. Ages are then kept non-decreasing so the Excel's
    approximate MATCH (sorted lookup) stays valid.
    """
    stages = [s.model_copy() for s in active_stages(inputs)]
    factor = inputs.career.bonus_factor
    for s in stages:
        s.bonus = s.bonus * factor
    md_age = inputs.career.md_age
    md_idx = next((i for i, s in enumerate(stages) if s.name.strip().upper() == "MD"), None)
    if md_age is not None and md_idx is not None:
        delta = md_age - stages[md_idx].age
        first = next(
            (i for i, s in enumerate(stages) if s.name.lower().startswith("director")), md_idx
        )
        for s in stages[first:]:
            s.age = s.age + delta
    for i in range(1, len(stages)):
        stages[i].age = max(stages[i].age, stages[i - 1].age)
    return stages


def effective_inputs(inputs: LifePlanInputs, live_wealth: float | None) -> LifePlanInputs:
    """Fold playground controls into plain values (what the Excel would hold).

    - career quick sliders → the stage table itself, sliders reset
    - wealth_source "dashboard" → ``start_wealth`` = live value (if known)
    """
    out = inputs.model_copy(deep=True)
    out.career.paths[out.career.path] = effective_stages(inputs)
    out.career.bonus_factor = 1.0
    out.career.md_age = None
    if inputs.start.wealth_source == "dashboard" and live_wealth is not None:
        out.start.start_wealth = float(live_wealth)
    return out
