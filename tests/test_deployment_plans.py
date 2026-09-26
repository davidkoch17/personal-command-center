"""Tests for modules/finance/deployment_plans.py and its endpoints (Chunk 6, C6).

The plans file is redirected to tmp_path so the real data/deployment_plans.jsonl
is never touched; "today" is injected wherever a countdown is computed.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.finance import deployment_plans as dp_api
from modules.finance import deployment_plans as dp

TODAY = date(2026, 1, 1)


@pytest.fixture(autouse=True)
def plans_file(monkeypatch, tmp_path):
    monkeypatch.setattr(dp, "DEPLOYMENT_PLANS_FILE", tmp_path / "deployment_plans.jsonl")
    return tmp_path / "deployment_plans.jsonl"


def _plan(**kw):
    kw.setdefault("name", "Q1 ETF boost")
    kw.setdefault("total_eur", 10000)
    kw.setdefault("start", TODAY)
    return dp.create_plan(**kw)


# --- creation / default schedule ---------------------------------------------------

def test_default_schedule_is_50_30_20_at_0_4_9_weeks():
    plan = _plan(target_bucket="etf_foundation")

    assert [t.pct for t in plan.schedule] == [50, 30, 20]
    assert [t.target_date for t in plan.schedule] == [TODAY, TODAY + timedelta(weeks=4), TODAY + timedelta(weeks=9)]
    assert all(not t.executed and t.amount_eur is None and t.trade_id is None for t in plan.schedule)
    assert plan.status == "in_progress" and plan.created_at == TODAY
    assert plan.id == "plan-2026-q1-etf-boost"


def test_create_persists_as_jsonl_and_ids_are_unique(plans_file):
    a = _plan()
    b = _plan()  # same name -> suffixed id, not an overwrite

    assert (a.id, b.id) == ("plan-2026-q1-etf-boost", "plan-2026-q1-etf-boost-2")
    assert len(plans_file.read_text(encoding="utf-8").splitlines()) == 2  # one JSON object per line
    assert [p.id for p in dp.list_plans()] == [a.id, b.id]


def test_custom_schedule_and_ticker_target():
    plan = _plan(
        target_ticker="vwce.de",
        schedule=[{"pct": 60, "target_date": "2026-02-01"}, {"pct": 40, "target_date": "2026-03-01"}],
    )
    assert plan.target_ticker == "VWCE.DE" and plan.target_bucket is None
    assert [t.pct for t in plan.schedule] == [60, 40]


@pytest.mark.parametrize("kwargs, msg", [
    ({"name": "  "}, "name"),
    ({"total_eur": 0}, "total_eur"),
    ({"total_eur": -5}, "total_eur"),
    ({"target_bucket": "crypto", "target_ticker": "BTC-USD"}, "not both"),
    ({"schedule": [{"pct": 50, "target_date": "2026-02-01"}, {"pct": 40, "target_date": "2026-03-01"}]}, "sum to 100"),
    ({"schedule": [{"pct": 110, "target_date": "2026-02-01"}, {"pct": -10, "target_date": "2026-03-01"}]}, "positive"),
])
def test_create_rejects_invalid_plans(kwargs, msg):
    with pytest.raises(dp.PlanError, match=msg):
        _plan(**kwargs)
    assert dp.list_plans() == []  # nothing half-written


# --- read / update / delete ---------------------------------------------------------

def test_list_filter_get_and_missing():
    a, b = _plan(name="A"), _plan(name="B")
    dp.update_plan(b.id, {"status": "cancelled"})

    assert [p.id for p in dp.list_plans("in_progress")] == [a.id]
    assert [p.id for p in dp.list_plans("cancelled")] == [b.id]
    assert dp.get_plan(a.id).name == "A"
    with pytest.raises(dp.NotFound):
        dp.get_plan("nope")


def test_update_edits_fields_and_switches_target():
    plan = _plan(target_bucket="crypto")

    out = dp.update_plan(plan.id, {"name": "Crypto DCA", "total_eur": 5000, "target_bucket": None, "target_ticker": "eth-usd"})

    assert (out.name, out.total_eur, out.target_bucket, out.target_ticker) == ("Crypto DCA", 5000, None, "ETH-USD")
    with pytest.raises(dp.PlanError, match="not both"):
        dp.update_plan(plan.id, {"target_bucket": "crypto"})  # ticker is still set


def test_update_tranche_dates_pending_only():
    plan = _plan()
    dp.mark_tranche_executed(plan.id, 0, 5000, TODAY)

    out = dp.update_plan(plan.id, {"tranche_dates": {"1": "2026-03-01"}})
    assert out.schedule[1].target_date == date(2026, 3, 1)
    with pytest.raises(dp.PlanError, match="already executed"):
        dp.update_plan(plan.id, {"tranche_dates": {"0": "2026-01-05"}})  # history is immutable
    with pytest.raises(dp.NotFound):
        dp.update_plan(plan.id, {"tranche_dates": {"9": "2026-01-05"}})


def test_delete_plan():
    a, b = _plan(name="A"), _plan(name="B")
    dp.delete_plan(a.id)
    assert [p.id for p in dp.list_plans()] == [b.id]
    with pytest.raises(dp.NotFound):
        dp.delete_plan(a.id)


def test_malformed_lines_are_skipped(plans_file):
    a = _plan()
    with plans_file.open("a", encoding="utf-8") as fh:
        fh.write("{not json\n\n")
    assert [p.id for p in dp.list_plans()] == [a.id]


# --- executing tranches --------------------------------------------------------------

def test_mark_tranche_executed_records_details():
    plan = _plan()

    out = dp.mark_tranche_executed(plan.id, 0, 4900.5, date(2026, 1, 3), trade_id=" tx-42 ")

    t = out.schedule[0]
    assert (t.executed, t.amount_eur, t.executed_date, t.trade_id) == (True, 4900.5, date(2026, 1, 3), "tx-42")
    assert not out.schedule[1].executed and out.status == "in_progress"
    assert dp.get_plan(plan.id).schedule[0].executed  # persisted


def test_execute_rules():
    plan = _plan()
    dp.mark_tranche_executed(plan.id, 1, 3000, TODAY)

    with pytest.raises(dp.PlanError, match="already executed"):
        dp.mark_tranche_executed(plan.id, 1, 3000, TODAY)
    with pytest.raises(dp.PlanError, match="positive"):
        dp.mark_tranche_executed(plan.id, 0, 0, TODAY)
    with pytest.raises(dp.NotFound):
        dp.mark_tranche_executed(plan.id, 7, 100, TODAY)
    dp.update_plan(plan.id, {"status": "cancelled"})
    with pytest.raises(dp.PlanError, match="cancelled"):
        dp.mark_tranche_executed(plan.id, 0, 100, TODAY)


def test_plan_completes_when_last_tranche_executes():
    plan = _plan()
    for i, amt in enumerate((5000, 3000, 2000)):
        out = dp.mark_tranche_executed(plan.id, i, amt, TODAY)
    assert out.status == "complete"


# --- progress -------------------------------------------------------------------------

def test_progress_sums_executed_tranche_pcts_and_next_countdown():
    plan = _plan()
    assert dp.plan_progress(plan, TODAY)["deployed_pct"] == 0

    plan = dp.mark_tranche_executed(plan.id, 0, 5000, TODAY)
    p = dp.plan_progress(plan, today=TODAY + timedelta(days=16))

    assert p["deployed_pct"] == 50 and p["deployed_eur"] == 5000 and p["planned_eur"] == 10000
    assert (p["executed_count"], p["tranche_count"]) == (1, 3)
    # Next = the 30% tranche, due day 28 -> 12 days from day 16 ("Next: 30% in 12 days").
    assert p["next_tranche"] == {"index": 1, "pct": 30, "target_date": "2026-01-29", "days_until": 12}


def test_overdue_tranche_has_negative_days_and_complete_plan_has_no_next():
    plan = _plan()
    late = dp.plan_progress(plan, today=TODAY + timedelta(days=5))["next_tranche"]
    assert late["index"] == 0 and late["days_until"] == -5

    for i in range(3):
        plan = dp.mark_tranche_executed(plan.id, i, 100, TODAY)
    assert dp.plan_progress(plan, TODAY)["next_tranche"] is None
    assert dp.plan_progress(plan, TODAY)["deployed_pct"] == 100


def test_progress_summary_counts_active_and_finds_soonest_due():
    a = _plan(name="A")  # first tranche due day 0
    b = _plan(name="B", start=TODAY + timedelta(days=10))  # first due day 10
    c = _plan(name="C")
    dp.update_plan(c.id, {"status": "cancelled"})
    dp.mark_tranche_executed(a.id, 0, 1, TODAY)  # A's next is now the day-28 tranche

    s = dp.progress_summary(dp.list_plans(), today=TODAY)

    assert (s["active_count"], s["total_count"]) == (2, 3)
    assert s["next_due"]["plan_name"] == "B" and s["next_due"]["days_until"] == 10
    assert dp.progress_summary([], TODAY) == {"active_count": 0, "total_count": 0, "next_due": None}


# --- endpoints --------------------------------------------------------------------------

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(dp_api.router, prefix="/api/finance")
    return TestClient(app)


def test_endpoint_lifecycle(client):
    base = "/api/finance/deployment-plans"
    assert client.get(base).json() == {"plans": [], "summary": {"active_count": 0, "total_count": 0, "next_due": None}}

    created = client.post(base, json={"name": "Q1 ETF boost", "total_eur": 10000, "target_bucket": "etf_foundation"}).json()
    pid = created["id"]
    assert [t["pct"] for t in created["schedule"]] == [50, 30, 20]
    assert created["progress"]["deployed_pct"] == 0

    listed = client.get(base).json()
    assert [p["id"] for p in listed["plans"]] == [pid] and listed["summary"]["active_count"] == 1

    done = client.post(f"{base}/{pid}/tranches/0/execute", json={"amount_eur": 5000, "executed_date": "2026-01-02"}).json()
    assert done["progress"]["deployed_pct"] == 50 and done["schedule"][0]["executed_date"] == "2026-01-02"

    patched = client.patch(f"{base}/{pid}", json={"name": "Renamed", "tranche_dates": {"1": "2026-03-05"}}).json()
    assert patched["name"] == "Renamed" and patched["schedule"][1]["target_date"] == "2026-03-05"

    assert client.get(f"{base}/{pid}").json()["name"] == "Renamed"
    assert client.get(f"{base}?status=complete").json()["plans"] == []
    assert client.delete(f"{base}/{pid}").json() == {"ok": True, "id": pid}
    assert client.get(base).json()["plans"] == []


def test_endpoint_errors(client):
    base = "/api/finance/deployment-plans"
    assert client.get(f"{base}/nope").status_code == 404
    assert client.delete(f"{base}/nope").status_code == 404
    assert client.post(base, json={"name": "x", "total_eur": -1}).status_code == 422
    assert client.post(base, json={"name": "x", "total_eur": 10, "target_bucket": "bogus"}).status_code == 422
    assert client.get(f"{base}?status=bogus").status_code == 422

    pid = client.post(base, json={"name": "x", "total_eur": 10}).json()["id"]
    assert client.post(f"{base}/{pid}/tranches/0/execute", json={"amount_eur": 5}).status_code == 200
    assert client.post(f"{base}/{pid}/tranches/0/execute", json={"amount_eur": 5}).status_code == 422  # twice
    assert client.post(f"{base}/{pid}/tranches/9/execute", json={"amount_eur": 5}).status_code == 404
    # A null in PATCH clears a target (only fields the client sent are touched).
    assert client.patch(f"{base}/{pid}", json={"target_ticker": "adbe"}).json()["target_ticker"] == "ADBE"
    assert client.patch(f"{base}/{pid}", json={"target_ticker": None}).json()["target_ticker"] is None
