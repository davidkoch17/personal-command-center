"""Lebensplan: golden test against the Excel, scenarios, promote, store."""
from __future__ import annotations

import shutil
from pathlib import Path

import openpyxl
import pytest

from core.config import LIFEPLAN_XLSX
from modules.lifeplan import excel_writer, scenarios
from modules.lifeplan.inputs import (
    CELL_MAP,
    LifePlanInputs,
    apply_overrides,
    deep_merge,
    diff,
    effective_inputs,
    effective_stages,
    read_inputs,
)
from modules.lifeplan.model import compute, excel_round, income_tax_2026

TOL = 1.0
TIMELINE_COLS = {
    "L": "net_income", "U": "spending", "V": "savings", "W": "purchases",
    "Y": "debt", "Z": "liquid", "AA": "real_assets", "AB": "net_worth",
}

needs_excel = pytest.mark.skipif(not LIFEPLAN_XLSX.exists(), reason="Traumleben_Plan.xlsx fehlt")


@pytest.fixture(scope="module")
def cached() -> openpyxl.Workbook:
    """Excel with cached values; skip if openpyxl wrote it last (no cache)."""
    wb = openpyxl.load_workbook(LIFEPLAN_XLSX, data_only=True)
    if wb["Zeitachse"]["AB5"].value is None:
        pytest.skip("Excel ohne berechnete Werte – einmal in Excel öffnen und speichern")
    return wb


@pytest.fixture(scope="module")
def base() -> LifePlanInputs:
    return read_inputs(LIFEPLAN_XLSX)


# --------------------------------------------------------------------------- golden
@needs_excel
def test_golden_timeline(cached, base):
    res = compute(base)
    ws = cached["Zeitachse"]
    assert len(res.years) == 50
    for i, y in enumerate(res.years):
        row = i + 5
        assert y.year == ws[f"A{row}"].value
        assert y.age == ws[f"B{row}"].value
        for col, attr in TIMELINE_COLS.items():
            expected = ws[f"{col}{row}"].value or 0
            assert getattr(y, attr) == pytest.approx(expected, abs=TOL), f"{col}{row}"
        assert y.warning == (ws[f"AD{row}"].value or ""), f"AD{row}"
        assert y.goal_reached == (ws[f"AC{row}"].value == "✅"), f"AC{row}"


@needs_excel
def test_golden_result_block(cached, base):
    s = compute(base).summary
    kd = cached["Key Drivers"]
    assert s.target == pytest.approx(kd["L5"].value, abs=TOL)
    expected_age = kd["L6"].value
    assert s.goal_age == (None if expected_age == "nicht bis 75" else expected_age)
    expected_year = kd["L7"].value
    assert s.goal_year == (None if expected_year == "–" else expected_year)
    for cell, age in zip(("L8", "L9", "L10", "L11", "L12", "L13"), (30, 35, 40, 45, 50, 55)):
        assert s.net_worth_at[age] == pytest.approx(kd[cell].value, abs=TOL), cell
    assert s.min_liquid == pytest.approx(kd["L14"].value, abs=TOL)
    assert s.warnings == kd["L15"].value


@needs_excel
def test_golden_milestones(cached, base):
    res = compute(base)
    ws = cached["Meilensteine"]
    for m in res.milestones:
        row = m.idx + 5
        for col, attr in (("C", "purchase_price"), ("D", "loan"), ("E", "equity"),
                          ("H", "reserve"), ("I", "liquid_needed"), ("N", "spending"),
                          ("P", "gross_income_needed")):
            assert getattr(m, attr) == pytest.approx(ws[f"{col}{row}"].value, abs=TOL), f"{col}{row}"


@needs_excel
def test_read_inputs_matches_defaults(base):
    assert base.start.birth_year == 2001
    stages = base.career.paths["banking"]
    assert len(stages) == 14 and stages[12].name == "MD"
    assert len(base.spending.bands) == 4


# --------------------------------------------------------------------------- scenarios
@needs_excel
def test_scenario_gruenwald_40_gymnasium_partner(base):
    inputs = apply_overrides(base, {
        "milestones": {"house_munich": 40},
        "assumptions": {"child_6_18": 600},
        "family": {"partner_gross": 80_000},
    })
    s = compute(inputs).summary
    assert s.min_liquid > 0
    assert s.warnings == 0


@needs_excel
def test_scenario_never_buy_houses_no_debt(base):
    res = compute(apply_overrides(base, {"milestones": {"house_munich": 999, "house_cape": 999}}))
    assert all(y.debt == 0 and y.loan_payment == 0 for y in res.years)
    assert res.summary.warnings == 0
    gr = next(m for m in res.milestones if m.key == "house_munich")
    assert gr.purchase_year is None and gr.financeable is None


def test_quick_sliders():
    stages = [
        {"name": "Analyst", "age": 25, "fix": 100, "bonus": 100},
        {"name": "VP", "age": 31, "fix": 100, "bonus": 100},
        {"name": "Director 1", "age": 34, "fix": 100, "bonus": 100},
        {"name": "MD", "age": 37, "fix": 100, "bonus": 100},
    ]
    inp = LifePlanInputs.model_validate(
        {"career": {"paths": {"banking": stages}, "bonus_factor": 0.5, "md_age": 35}}
    )
    eff = effective_stages(inp)
    assert [s.bonus for s in eff] == [50] * 4
    assert [s.age for s in eff] == [25, 31, 32, 35]
    # shifting far down keeps ages sorted
    inp.career.md_age = 30
    assert [s.age for s in effective_stages(inp)] == [25, 31, 31, 31]
    folded = effective_inputs(inp, live_wealth=None)
    assert folded.career.bonus_factor == 1.0 and folded.career.md_age is None


def test_dashboard_wealth_source():
    inp = LifePlanInputs.model_validate({"start": {"start_wealth": 10_000, "wealth_source": "dashboard"}})
    assert effective_inputs(inp, 4525.09).start.start_wealth == 4525.09
    assert effective_inputs(inp, None).start.start_wealth == 10_000


def test_tax_helpers():
    assert income_tax_2026(12_000) == 0
    assert excel_round(income_tax_2026(120_021.6)) == 39273
    assert excel_round(2.5) == 3 and excel_round(-2.5) == -3


def test_diff_roundtrip():
    a = {"x": 1, "n": {"a": 1, "b": 2}, "l": [1, 2]}
    b = {"x": 1, "n": {"a": 1, "b": 3}, "l": [1, 2, 3]}
    d = diff(a, b)
    assert d == {"n": {"b": 3}, "l": [1, 2, 3]}
    assert deep_merge(a, d) == b


# --------------------------------------------------------------------------- store
def test_scenario_store(tmp_path: Path):
    path = tmp_path / "scenarios.json"
    s1 = scenarios.save_scenario(path, "Grünwald mit 40", {"milestones": {"house_munich": 40}})
    assert s1["id"] == "grunwald-mit-40"
    s2 = scenarios.save_scenario(path, "Grünwald mit 40", {"milestones": {"house_munich": 41}})
    assert s2["id"] == s1["id"]  # same name overwrites
    scenarios.save_scenario(path, "Andere", {})
    data = scenarios.load(path)
    assert data["version"] == 1 and len(data["scenarios"]) == 2
    assert data["scenarios"][0]["overrides"] == {"milestones": {"house_munich": 41}}
    scenarios.delete_scenario(path, s1["id"])
    assert [s["name"] for s in scenarios.list_scenarios(path)] == ["Andere"]
    with pytest.raises(KeyError):
        scenarios.delete_scenario(path, "gibt-es-nicht")


# --------------------------------------------------------------------------- promote
def _formulas(xlsx: Path) -> dict[str, str]:
    wb = openpyxl.load_workbook(xlsx)
    return {
        f"{ws.title}!{c.coordinate}": c.value
        for ws in wb for row in ws.iter_rows() for c in row
        if isinstance(c.value, str) and c.value.startswith("=")
    }


@needs_excel
def test_promote_writes_only_inputs(tmp_path: Path, base):
    xlsx = tmp_path / "Traumleben_Plan.xlsx"
    shutil.copy2(LIFEPLAN_XLSX, xlsx)
    before = _formulas(xlsx)
    new = apply_overrides(base, {
        "milestones": {"house_munich": 40},
        "assumptions": {"rent_today": 1234},
        "career": {"bonus_factor": 0.8},
    })
    info = excel_writer.write_inputs(xlsx, effective_inputs(new, None), backup_dir=tmp_path / "backup")
    assert Path(info["backup"]).exists()
    assert _formulas(xlsx) == before
    assert "Key Drivers!C46" in info["changed"] and "Annahmen!B43" in info["changed"]
    reread = read_inputs(xlsx)
    assert reread.milestones.house_munich == 40
    assert reread.assumptions.rent_today == 1234
    assert reread.career.paths["banking"][0].bonus == pytest.approx(base.career.paths["banking"][0].bonus * 0.8)
    # input cells untouched by the change keep their value
    assert reread.assumptions.fx_eur_zar == base.assumptions.fx_eur_zar


def test_cell_map_has_no_duplicates():
    refs = [(s, c) for s, c, _ in CELL_MAP]
    assert len(refs) == len(set(refs))
