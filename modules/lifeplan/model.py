"""Pure-Python re-implementation of the ``Traumleben_Plan.xlsx`` formulas.

The Excel formulas are the specification. Column letters in comments refer to
the ``Zeitachse`` tab (rows 5–54 = 50 plan years), cell refs to the
``Meilensteine`` / ``Traumleben Einmalig`` tabs. No I/O in this module.

All amounts are in today's purchasing power (€).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from modules.lifeplan.inputs import (
    CAPE_HOUSE_ZAR,
    CareerStage,
    LifePlanInputs,
    effective_stages,
)

PLAN_YEARS = 50
NEVER = 999
WARN_NEGATIVE = "⚠ Liquidität negativ"
WARN_RESERVE = "⚠ Reserve < 6 Monate"
REPORT_AGES = (30, 35, 40, 45, 50, 55)

# Milestone keys in the order of the Meilensteine tab rows 7–11.
MILESTONE_KEYS = ("main_car", "fun_car", "house_munich", "sports_car", "house_cape")
MILESTONE_LABELS = {
    "main_car": "Main Car",
    "fun_car": "Spaßauto / Oldtimer",
    "house_munich": "Familienhaus Grünwald",
    "sports_car": "Sportwagen",
    "house_cape": "Haus Kapstadt",
}


# --------------------------------------------------------------------------- results
@dataclass
class OneOffRow:
    key: str
    label: str
    price: float          # E — Ansatz
    fees_pct: float       # F
    fees: float           # G
    total: float          # H


@dataclass
class MilestoneRow:
    idx: int
    key: Optional[str]
    label: str
    purchase_price: float     # C — Kaufpreis inkl. NK
    loan: float               # D
    equity: float             # E
    fees_lost: float          # F
    in_asset: float           # G
    reserve: float            # H
    liquid_needed: float      # I
    living: float             # J (inkl. Puffer, €/Mon.)
    car_depreciation: float   # K (€/Mon.)
    loan_payment: float       # L (€/Mon.)
    amortization: float       # M (€/Mon.)
    spending: float           # N (€/Mon.)
    net_income_needed: float  # O (€/Jahr)
    gross_income_needed: float  # P (€/Jahr)
    purchase_age: Optional[float] = None
    purchase_year: Optional[int] = None
    financeable: Optional[bool] = None   # no warning in the purchase year


@dataclass
class YearRow:
    year: int
    age: float
    salary: float           # C
    social: float           # D
    partner_gross: float    # E
    partner_social: float   # F
    taxable: float          # G
    splitting: float        # H
    income_tax: float       # I
    soli_church: float      # J
    employer_pkv: float     # K
    net_income: float       # L
    spend_pct: float        # M
    lifestyle: float        # N
    rent: float             # O
    kids: float             # P
    insurance: float        # Q
    homes_cars: float       # R
    buffer: float           # S
    loan_payment: float     # T
    spending: float         # U
    savings: float          # V
    purchases: float        # W
    new_loan: float         # X
    debt: float             # Y
    liquid: float           # Z
    real_assets: float      # AA
    net_worth: float        # AB
    goal_reached: bool      # AC
    warning: str            # AD
    purchased: list[str] = field(default_factory=list)


@dataclass
class Summary:
    target: float                        # Key Drivers L5
    goal_age: Optional[float]            # L6 (None = "nicht bis 75")
    goal_year: Optional[int]             # L7
    net_worth_at: dict[int, Optional[float]]  # L8:L13
    min_liquid: float                    # L14
    warnings: int                        # L15


@dataclass
class LifePlanResult:
    summary: Summary
    years: list[YearRow]
    milestones: list[MilestoneRow]
    one_off: list[OneOffRow]
    lifestyle_variable_monthly: float    # Key Drivers C35
    one_off_total: float                 # Traumleben Einmalig H10
    running_total_monthly: float         # Laufende Kosten C17
    career: list[dict[str, Any]]         # effective stage table

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly dict (int keys of net_worth_at become strings)."""
        out = asdict(self)
        out["summary"]["net_worth_at"] = {
            str(k): v for k, v in self.summary.net_worth_at.items()
        }
        return out


# --------------------------------------------------------------------------- helpers
def excel_round(x: float, digits: int = 0) -> float:
    """Excel ROUND: half away from zero."""
    f = 10.0 ** digits
    return math.copysign(math.floor(abs(x) * f + 0.5) / f, x)


def income_tax_2026(zve: float) -> float:
    """§ 32a EStG 2026 tariff for one person (unrounded), as in the Excel."""
    if zve <= 12348:
        return 0.0
    if zve <= 17799:
        y = (zve - 12348) / 10000
        return (914.51 * y + 1400) * y
    if zve <= 69878:
        z = (zve - 17799) / 10000
        return (173.1 * z + 2397) * z + 1034.87
    if zve <= 277825:
        return 0.42 * zve - 11135.63
    return 0.45 * zve - 19470.38


def lookup_le(keys: list[float], values: list[float], x: float) -> Optional[float]:
    """Excel ``INDEX(values, MATCH(x, keys, 1))`` for ascending keys.

    Returns ``None`` where Excel would give #N/A (x below the first key).
    """
    result: Optional[float] = None
    for k, v in zip(keys, values):
        if k <= x:
            result = v
        else:
            break
    return result


def child_monthly(delta: float, inputs: LifePlanInputs) -> float:
    """Monthly child cost by the child's age (``delta`` = your age − birth age)."""
    a = inputs.assumptions
    if delta < 0:
        return 0.0
    if delta < 6:
        return a.child_0_5
    if delta < 19:
        return a.child_6_18
    if delta < 25:
        return a.child_19_24
    return 0.0


# --------------------------------------------------------------------------- one-off
def compute_one_off(inputs: LifePlanInputs) -> list[OneOffRow]:
    """Traumleben Einmalig rows 5–9 (E, F, G, H)."""
    a, o = inputs.assumptions, inputs.one_off
    rows: list[OneOffRow] = []
    de_fees = a.de_transfer_tax + a.de_notary + a.de_broker            # F5
    rows.append(OneOffRow("house_munich", "Haus München (Grünwald)", o.house_munich.price,
                          de_fees, o.house_munich.price * de_fees,
                          o.house_munich.price * (1 + de_fees)))
    cape_price = CAPE_HOUSE_ZAR / a.fx_eur_zar                         # E6
    za_fees = a.za_transfer_duty + a.za_legal                          # F6
    rows.append(OneOffRow("house_cape", "Haus Kapstadt", cape_price, za_fees,
                          cape_price * za_fees, cape_price * (1 + za_fees)))
    for key, label in (("main_car", "Auto 1 – Main Car"),
                       ("sports_car", "Auto 2 – Sportwagen"),
                       ("fun_car", "Auto 3 – Spaß/Oldtimer")):
        car = getattr(o, key)
        fees = car.price * car.fees_pct
        rows.append(OneOffRow(key, label, car.price, car.fees_pct, fees, car.price + fees))
    return rows


# --------------------------------------------------------------------------- milestones
def compute_milestones(inputs: LifePlanInputs, one_off: list[OneOffRow]) -> tuple[list[MilestoneRow], float]:
    """Meilensteine rows 5–11 plus the target wealth (I24)."""
    a, r = inputs.assumptions, inputs.running
    oo = {row.key: row for row in one_off}
    buf = r.buffer

    # T column: living cost without buffer, cumulative per stage.
    t0 = a.living_today
    t2 = t0 + a.upkeep_main_car
    t3 = t2 + a.upkeep_fun_car
    t4 = (t3 - a.living_today + r.house_munich + r.household_help + r.groceries + r.dining
          + r.kids + a.travel_before_cape + r.leisure + r.insurance + r.misc)
    t5 = t4 + a.upkeep_sports_car
    t6 = t5 + r.house_cape + (r.travel - a.travel_before_cape)
    t_col = [t0, t0, t2, t3, t4, t5, t6]

    # V column: car depreciation per month.
    v_col = [0.0, 0.0,
             inputs.one_off.main_car.price * a.depr_main_car / 12,
             inputs.one_off.fun_car.price * a.depr_fun_car / 12,
             0.0,
             inputs.one_off.sports_car.price * a.depr_sports_car / 12,
             0.0]

    specs = [  # (key, label, C, D, F)
        (None, "Heute", 0.0, 0.0, 0.0),
        (None, "Fundament: Reserve aufbauen", 0.0, 0.0, 0.0),
        ("main_car", "Main Car", oo["main_car"].total, 0.0, 0.0),
        ("fun_car", "Spaßauto / Oldtimer", oo["fun_car"].total, 0.0, 0.0),
        ("house_munich", "Familienhaus Grünwald", oo["house_munich"].total,
         inputs.one_off.house_munich.price * a.ltv, oo["house_munich"].fees),
        ("sports_car", "Sportwagen", oo["sports_car"].total, 0.0, 0.0),
        ("house_cape", "Haus Kapstadt", oo["house_cape"].total,
         oo["house_cape"].total * (1 - a.za_equity_share), oo["house_cape"].fees),
    ]

    rows: list[MilestoneRow] = []
    loans_cum = 0.0
    depr_cum = 0.0
    for idx, ((key, label, c, d, f), t, v) in enumerate(zip(specs, t_col, v_col)):
        e = c - d
        g = e - f
        j = t * (1 + buf)
        depr_cum += v
        loans_cum += d
        l_ = loans_cum * (a.mortgage_rate + a.amortization) / 12
        m = loans_cum * a.amortization / 12
        n = j + depr_cum + l_
        h = 0.0 if idx == 0 else n * a.reserve_months
        o = max(0.0, (n - a.partner_net_monthly) * 12)
        p = o / a.net_ratio if a.net_ratio else 0.0
        rows.append(MilestoneRow(idx, key, label, c, d, e, f, g, h, e + h, j, depr_cum,
                                 l_, m, n, o, p))

    last = rows[-1]
    one_off_total = sum(row.total for row in one_off)                  # I21
    denom = a.withdrawal_rate * (1 - a.withdrawal_tax)
    depot = (last.living + last.car_depreciation) * 12 / denom if denom else math.inf  # I22
    target = one_off_total + depot + last.reserve                      # I24
    return rows, target


# --------------------------------------------------------------------------- timeline
def compute(inputs: LifePlanInputs) -> LifePlanResult:
    """Run the full model: one-off costs, milestones, 50-year timeline, summary."""
    a, f, ms, r = inputs.assumptions, inputs.family, inputs.milestones, inputs.running
    stages: list[CareerStage] = effective_stages(inputs)
    stage_ages = [s.age for s in stages]
    stage_comp = [s.fix + s.bonus for s in stages]
    bands = inputs.spending.bands
    band_ages = [b.age for b in bands]
    band_pcts = [b.pct for b in bands]

    one_off = compute_one_off(inputs)
    oo = {row.key: row for row in one_off}
    milestones, target = compute_milestones(inputs, one_off)
    mrow = {m.key: m for m in milestones if m.key}
    munich_loan = mrow["house_munich"].loan                            # Meilensteine D9
    v_main = inputs.one_off.main_car.price * a.depr_main_car / 12      # V7
    v_fun = inputs.one_off.fun_car.price * a.depr_fun_car / 12         # V8
    v_sports = inputs.one_off.sports_car.price * a.depr_sports_car / 12  # V10

    lifestyle_var = (r.household_help + r.groceries + r.dining + r.travel + r.leisure
                     + r.misc)                                         # Key Drivers C35
    social_rate = a.pension_rate + a.unemployment_rate
    buf = r.buffer

    years: list[YearRow] = []
    prev_debt = 0.0
    prev_liquid = inputs.start.start_wealth
    prev_goal = False
    for i in range(PLAN_YEARS):
        year = inputs.start.start_year + i                             # A
        age = year - inputs.start.birth_year                           # B
        married = age >= f.marriage_age
        mult = 2 if married else 1

        if age > inputs.career.work_until_age:                         # C
            salary = 0.0
        else:
            salary = lookup_le(stage_ages, stage_comp, age) or 0.0
        social = min(salary, a.bbg) * social_rate                      # D
        partner = f.partner_gross if married else 0.0                  # E
        partner_social = min(partner, a.bbg) * social_rate             # F
        taxable = max(0.0, salary - social - a.werbungskosten - a.health_deductible)  # G
        if married:
            taxable += max(0.0, partner - partner_social - a.werbungskosten - a.health_deductible)
        splitting = taxable / 2 if married else taxable                # H
        income_tax = excel_round(income_tax_2026(splitting) * mult)    # I
        soli_church = (min(0.055 * income_tax,
                           0.119 * max(0.0, income_tax - a.soli_threshold * mult))
                       + income_tax * a.church_tax)                    # J
        employer_pkv = a.employer_pkv * 12 if salary > 0 else 0.0      # K
        net = salary + partner - social - partner_social - income_tax - soli_church + employer_pkv  # L

        if i > 0 and prev_goal:                                        # M
            pct = 1.0
        else:
            looked = lookup_le(band_ages, band_pcts, age)
            pct = looked if looked is not None else (band_pcts[0] if band_pcts else 0.0)
        lifestyle = max(pct * lifestyle_var, a.min_living) * 12        # N

        kids_born = (age >= f.child1_age) + (age >= f.child2_age)
        if age >= ms.house_munich:                                     # O
            rent = 0.0
        else:
            rent = (a.rent_family if kids_born > 0 else a.rent_today) * 12
        kids = (child_monthly(age - f.child1_age, inputs)
                + child_monthly(age - f.child2_age, inputs)) * 12      # P
        insurance = (a.pkv_self + a.bu_insurance + (a.pkv_partner if married else 0.0)
                     + kids_born * a.pkv_child) * 12                   # Q
        homes_cars = ((a.upkeep_main_car + v_main if age >= ms.main_car else 0.0)
                      + (a.upkeep_fun_car + v_fun if age >= ms.fun_car else 0.0)
                      + (a.upkeep_sports_car + v_sports if age >= ms.sports_car else 0.0)
                      + (r.house_munich if age >= ms.house_munich else 0.0)
                      + (r.house_cape if age >= ms.house_cape else 0.0)) * 12  # R
        buffer = (lifestyle + rent + kids + insurance + homes_cars) * buf  # S

        new_loan = munich_loan if age == ms.house_munich else 0.0      # X
        outstanding = prev_debt + new_loan
        if outstanding > 0:                                            # T
            loan_payment = min(munich_loan * (a.mortgage_rate + a.amortization),
                               outstanding * (1 + a.mortgage_rate))
        else:
            loan_payment = 0.0
        spending = lifestyle + rent + kids + insurance + homes_cars + buffer + loan_payment  # U
        savings = net - spending                                       # V

        purchased = [k for k in MILESTONE_KEYS if age == getattr(ms, k)]
        purchases = sum(mrow[k].equity for k in purchased)             # W
        debt = max(0.0, outstanding * (1 + a.mortgage_rate) - loan_payment)  # Y
        liquid = prev_liquid * (1 + a.return_liquid) + savings - purchases  # Z

        real = 0.0                                                     # AA
        if age >= ms.house_munich:
            real += inputs.one_off.house_munich.price - debt
        if age >= ms.house_cape:
            real += oo["house_cape"].price
        if age >= ms.main_car:
            real += inputs.one_off.main_car.price * max(0.0, 1 - a.depr_main_car * (age - ms.main_car))
        if age >= ms.fun_car:
            real += inputs.one_off.fun_car.price * max(0.0, 1 - a.depr_fun_car * (age - ms.fun_car))
        if age >= ms.sports_car:
            real += inputs.one_off.sports_car.price * max(0.0, 1 - a.depr_sports_car * (age - ms.sports_car))

        net_worth = liquid + real                                      # AB
        goal = net_worth >= target                                     # AC
        if liquid < 0:                                                 # AD
            warning = WARN_NEGATIVE
        elif purchases > 0 and liquid < spending / 2:
            warning = WARN_RESERVE
        else:
            warning = ""

        years.append(YearRow(
            year, age, salary, social, partner, partner_social, taxable, splitting,
            income_tax, soli_church, employer_pkv, net, pct, lifestyle, rent, kids,
            insurance, homes_cars, buffer, loan_payment, spending, savings, purchases,
            new_loan, debt, liquid, real, net_worth, goal, warning, purchased,
        ))
        prev_debt, prev_liquid, prev_goal = debt, liquid, goal

    # Milestone purchase info + "financeable in purchase year?"
    by_age = {y.age: y for y in years}
    for m in milestones:
        if not m.key:
            continue
        age = getattr(ms, m.key)
        m.purchase_age = age
        row = by_age.get(age)
        if row is not None:
            m.purchase_year = row.year
            m.financeable = row.warning == ""

    goal_row = next((y for y in years if y.goal_reached), None)
    summary = Summary(
        target=target,
        goal_age=goal_row.age if goal_row else None,
        goal_year=goal_row.year if goal_row else None,
        net_worth_at={a_: (by_age[a_].net_worth if a_ in by_age else None) for a_ in REPORT_AGES},
        min_liquid=min(y.liquid for y in years),
        warnings=sum(1 for y in years if y.warning.startswith("⚠")),
    )
    running_total = sum(
        getattr(r, k) for k in ("house_munich", "house_cape", "household_help", "cars",
                                "groceries", "dining", "kids", "travel", "leisure",
                                "insurance", "misc")
    ) * (1 + buf)
    return LifePlanResult(
        summary=summary,
        years=years,
        milestones=milestones,
        one_off=one_off,
        lifestyle_variable_monthly=lifestyle_var,
        one_off_total=sum(row.total for row in one_off),
        running_total_monthly=running_total,
        career=[s.model_dump() for s in stages],
    )
