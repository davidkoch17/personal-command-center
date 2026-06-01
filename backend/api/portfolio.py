"""Portfolio API — wraps modules.finance.portfolio (Finance_Tracker.xlsx + yfinance)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.api._helpers import df_records, clean
from modules.finance import portfolio, money

router = APIRouter()


@router.get("")
def snapshot() -> dict:
    """Full portfolio snapshot: holdings table (live perf), totals, deployable cash."""
    holdings = portfolio.holdings_with_performance()
    metrics = portfolio.summary_metrics()
    records = df_records(holdings)
    market_total = sum(r.get("Market Value (€)") or 0 for r in records)
    return {
        "total_value": clean(metrics.get("total_value")) or 0.0,
        "position_count": metrics.get("position_count", 0),
        "last_snapshot_date": clean(metrics.get("latest_snapshot")),
        "market_value_total": market_total,
        "cash_deployable": money.current_cash_balance(),
        "holdings": records,
    }


@router.get("/performance")
def performance(period: str = Query("ytd")) -> dict:
    """Portfolio value over time (TR / Crypto / Total) with a period-window return."""
    by_month = portfolio.portfolio_value_by_month()
    series = df_records(by_month)
    change_pct = None
    if series:
        totals = [r.get("Total") for r in series if r.get("Total") is not None]
        if len(totals) >= 2 and totals[0]:
            change_pct = (totals[-1] - totals[0]) / totals[0] * 100.0
    return {"period": period, "by_month": series, "change_pct": change_pct}


@router.get("/allocations")
def allocations() -> dict:
    """Allocation breakdowns by instrument type and by position (value-weighted)."""
    holdings = portfolio.combined_holdings()
    records = df_records(holdings)
    total = sum(r.get("Value (€)") or 0 for r in records) or 0.0

    by_type: dict[str, float] = {}
    by_position: list[dict] = []
    for r in records:
        val = r.get("Value (€)") or 0.0
        typ = r.get("Type") or "Unknown"
        by_type[typ] = by_type.get(typ, 0.0) + val
        by_position.append({
            "name": r.get("Name"),
            "type": typ,
            "value": val,
            "weight_pct": (val / total * 100.0) if total else None,
        })

    return {
        "total_value": total,
        "by_type": [
            {"type": k, "value": v, "weight_pct": (v / total * 100.0) if total else None}
            for k, v in by_type.items()
        ],
        "by_position": sorted(by_position, key=lambda x: x["value"], reverse=True),
    }
