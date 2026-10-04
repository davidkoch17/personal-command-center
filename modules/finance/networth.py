"""Net Worth pillar (Chunk 9.7): the 4th sidebar pillar, a holistic breakdown
across bank cash, brokerage cash, and portfolio holdings by bucket.

This is deliberately a *separate* read path from the Portfolio pillar's
existing ``period_pnl.month_decomposition``/``networth_bridge`` (which are
live-ledger analytics scoped to "what moved the portfolio this month") and
from Excel's ``money.latest_net_worth()`` (the authoritative hand-recorded
figure elsewhere in the app). This pillar's number is its own: bank + brokerage
cash from ``cashflow_accounts.json`` plus live-priced holdings from
``positions.py``, independent of both. The two *will* disagree in general for
the same reasons ``period_pnl`` already documents — this module doesn't
reconcile them, only computes its own bottom-up total.

``data/cashflow_accounts.json`` has no explicit ``type`` field today (just
name/balance/is_reserve — see :mod:`modules.finance.cashflow`), so bank vs.
brokerage-cash classification here is a small name-pattern heuristic
(:func:`_account_class`), correct for the two accounts that exist (Haspa
Girokonto, Trade Republic Cash). If/when a third account of an ambiguous kind
shows up, this is the one place to extend.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import yaml

from core.config import BUCKET_LABELS, NETWORTH_DAILY_CSV, NETWORTH_TARGETS_FILE, get_logger
from modules.finance import cashflow
from modules.finance._csv_store import read_rows
from modules.finance.buckets import resolve_bucket
from modules.finance.positions import cost_basis, current_holdings, get_position
from modules.finance.price_history import get_closes, latest_price_eur

logger = get_logger(__name__)

PERIOD_DAYS: dict[str, Optional[int]] = {"1M": 30, "3M": 90, "1Y": 365, "YTD": None, "ALL": None}

# Trailing-window lookbacks for the per-holding price-change columns (Section 4).
PCT_WINDOWS = {"pct_1m": 30, "pct_1y": 365}

MILESTONE_LOOKBACK_DAYS = 90


def _account_class(name: str) -> str:
    """"bank_cash" / "brokerage_cash" / "liability" for one
    ``cashflow_accounts.json`` entry.

    Name-pattern heuristic (see module docstring) rather than a schema field —
    correct for Haspa Girokonto (bank) and Trade Republic Cash (brokerage); no
    liability-type account exists yet, but the branch is real (not a stub) so
    a future "Car Loan" or similar subtracts from the total the moment it's
    added, with no code change needed.
    """
    n = name.lower()
    if "loan" in n or "debt" in n or "mortgage" in n:
        return "liability"
    if "trade republic" in n or "brokerage" in n:
        return "brokerage_cash"
    return "bank_cash"


def compute_breakdown() -> dict:
    """Asset-class totals for the hero donut: cash (bank/brokerage) + holdings
    by bucket, plus liabilities (none tracked yet) and the grand total.
    """
    bank_cash = 0.0
    brokerage_cash = 0.0
    liabilities = 0.0
    for a in cashflow.list_accounts():
        cls = _account_class(a["name"])
        if cls == "brokerage_cash":
            brokerage_cash += a["balance"]
        elif cls == "liability":
            liabilities += a["balance"]
        else:
            bank_cash += a["balance"]

    by_bucket: dict[str, float] = {"etf_foundation": 0.0, "single_stocks": 0.0, "crypto": 0.0, "wild_cards": 0.0}
    for ticker, qty in current_holdings().items():
        lp = latest_price_eur(ticker)
        value = (lp.eur_price * qty) if lp else 0.0
        bucket = resolve_bucket(ticker)
        # An unresolved ("unassigned") ticker still has to land in the total —
        # concentration_alerts (Chunk 9.5) flags it on the Portfolio side, so
        # it isn't silently dropped here; it just doesn't get its own slice.
        by_bucket[bucket] = by_bucket.get(bucket, 0.0) + value

    total = round(
        bank_cash + brokerage_cash + sum(by_bucket.values()) - liabilities, 2
    )
    return {
        "bank_cash": round(bank_cash, 2),
        "brokerage_cash": round(brokerage_cash, 2),
        "etfs": round(by_bucket["etf_foundation"], 2),
        "single_stocks": round(by_bucket["single_stocks"], 2),
        "crypto": round(by_bucket["crypto"], 2),
        "wild_cards": round(by_bucket["wild_cards"], 2),
        "liabilities": round(liabilities, 2),
        "total": total,
    }


def _month_ago_total() -> Optional[float]:
    """``net_worth_eur`` from ``networth_daily.csv`` ~30 days ago (None if the
    history doesn't reach back that far), for the hero donut's "Δ this month".
    """
    rows = sorted(read_rows(NETWORTH_DAILY_CSV), key=lambda r: r.get("date", ""))
    if not rows:
        return None
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    baseline = None
    for r in rows:
        if r.get("date", "") <= cutoff:
            baseline = r
        else:
            break
    if baseline is None:
        return None
    try:
        return float(baseline.get("net_worth_eur") or 0.0)
    except (TypeError, ValueError):
        return None


def compute_delta_this_month() -> Optional[float]:
    """Current total minus the total ~30 days ago (None if not enough history)."""
    month_ago = _month_ago_total()
    if month_ago is None:
        return None
    return round(compute_breakdown()["total"] - month_ago, 2)


def compute_trend(period: str = "3M") -> dict:
    """``{period, series, available}`` time series from ``networth_daily.csv``
    for the Section 2 sparkline. ``available`` is False only when the ledger
    has no history at all yet (brand-new setup), not merely a short window.
    """
    rows = sorted(read_rows(NETWORTH_DAILY_CSV), key=lambda r: r.get("date", ""))
    if not rows:
        return {"period": period, "series": [], "available": False}

    if period == "YTD":
        cutoff = date(date.today().year, 1, 1).isoformat()
        rows = [r for r in rows if r.get("date", "") >= cutoff]
    elif period != "ALL":
        days = PERIOD_DAYS.get(period, 90)
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        rows = [r for r in rows if r.get("date", "") >= cutoff]

    series = []
    for r in rows:
        try:
            series.append({"date": r["date"], "net_worth_eur": round(float(r.get("net_worth_eur") or 0.0), 2)})
        except (TypeError, ValueError):
            continue
    return {"period": period, "series": series, "available": True}


def _load_current_goal() -> Optional[dict]:
    if not NETWORTH_TARGETS_FILE.exists():
        return None
    try:
        raw = yaml.safe_load(NETWORTH_TARGETS_FILE.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as exc:  # noqa: BLE001
        logger.warning("networth_targets.yaml unreadable: %s", exc)
        return None
    return raw.get("current_goal")


def compute_milestone_projection(target_eur: Optional[float] = None) -> dict:
    """Progress + a linear-trend projection toward a savings milestone.

    ``target_eur`` defaults to ``config/networth_targets.yaml``'s current
    goal. ``status`` is one of ``"on_track"`` (positive 3-month trend),
    ``"paused"`` (flat/negative trend), ``"reached"``, or
    ``"insufficient_history"`` (<90 days of ``networth_daily.csv`` history).
    """
    goal = _load_current_goal()
    label = goal.get("label") if goal else "Net worth goal"
    if target_eur is None:
        target_eur = float(goal["target_eur"]) if goal else None
    if target_eur is None:
        return {"available": False, "reason": "no goal configured in networth_targets.yaml"}

    current = compute_breakdown()["total"]
    pct = round(min(current / target_eur, 1.0) * 100, 1) if target_eur else None

    base = {
        "available": True,
        "label": label,
        "current": current,
        "target": target_eur,
        "pct": pct,
    }

    if current >= target_eur:
        return {**base, "monthly_rate": None, "months_to_goal": None, "projected_date": None, "status": "reached"}

    rows = sorted(read_rows(NETWORTH_DAILY_CSV), key=lambda r: r.get("date", ""))
    cutoff = date.today() - timedelta(days=MILESTONE_LOOKBACK_DAYS)
    baseline_row = None
    for r in rows:
        if r.get("date", "") <= cutoff.isoformat():
            baseline_row = r
        else:
            break
    if baseline_row is None:
        return {**base, "monthly_rate": None, "months_to_goal": None, "projected_date": None,
                "status": "insufficient_history"}

    try:
        nw_90d_ago = float(baseline_row.get("net_worth_eur") or 0.0)
    except (TypeError, ValueError):
        nw_90d_ago = 0.0
    monthly_rate = round((current - nw_90d_ago) / 3, 2)

    if monthly_rate <= 0:
        return {**base, "monthly_rate": monthly_rate, "months_to_goal": None, "projected_date": None,
                "status": "paused"}

    months_to_goal = round((target_eur - current) / monthly_rate, 1)
    projected_date = (date.today() + timedelta(days=months_to_goal * 30.44)).isoformat()
    return {**base, "monthly_rate": monthly_rate, "months_to_goal": months_to_goal,
            "projected_date": projected_date, "status": "on_track"}


def pct_change(ticker: str, days: int, *, on: Optional[date] = None) -> Optional[float]:
    """% price change over the trailing ``days`` calendar days (native
    currency — same convention as :func:`modules.finance.price_history.get_returns`
    elsewhere in the app). ``None`` when the cached price history doesn't
    reach back that far yet (a newly-listed asset, not merely a new position —
    see :func:`compute_accounts_hierarchy`'s docstring).
    """
    on = on or date.today()
    closes = get_closes(ticker)
    if closes.empty:
        return None
    up_to_on = closes[closes.index.date <= on]
    if up_to_on.empty:
        return None
    first_date = up_to_on.index.min().date()
    if (on - first_date).days < days:
        return None
    past = up_to_on[up_to_on.index.date <= on - timedelta(days=days)]
    if past.empty:
        return None
    past_price = float(past.iloc[-1])
    latest = float(up_to_on.iloc[-1])
    if not past_price:
        return None
    return round((latest - past_price) / past_price * 100, 2)


def compute_accounts_hierarchy() -> dict:
    """Nested CASH / PORTFOLIO breakdown for Section 4.

    Per-holding ``pct_1m``/``pct_1y`` are the *asset's* trailing price change
    (yfinance history, which usually spans years regardless of when David
    actually bought it) — not "how long David has held the position". A
    brand-new position can still show a real 1M/1Y% once the ticker itself
    has that much trading history; ``None`` only when the ticker's own cached
    price series doesn't reach back far enough (a genuinely new listing).
    """
    accounts = cashflow.list_accounts()
    cash_children = [{"name": a["name"], "value": round(a["balance"], 2)} for a in accounts]
    cash_total = round(sum(c["value"] for c in cash_children), 2)

    portfolio_children = []
    for ticker, qty in sorted(current_holdings().items()):
        meta = get_position(ticker)
        lp = latest_price_eur(ticker)
        value = round(lp.eur_price * qty, 2) if lp else 0.0
        _, total_basis = cost_basis(ticker)
        gain = round(value - total_basis, 2) if lp else None
        portfolio_children.append({
            "ticker": ticker,
            "name": meta.name if meta else ticker,
            "value": value,
            "pct_1m": pct_change(ticker, PCT_WINDOWS["pct_1m"]),
            "pct_1y": pct_change(ticker, PCT_WINDOWS["pct_1y"]),
            "gain": gain,
        })
    portfolio_total = round(sum(c["value"] for c in portfolio_children), 2)

    return {
        "cash": {"total": cash_total, "accounts": cash_children},
        "portfolio": {"total": portfolio_total, "holdings": portfolio_children},
    }


def snapshot(period: str = "3M") -> dict:
    """Everything the Net Worth page needs for first paint, in one call."""
    breakdown = compute_breakdown()
    return {
        "breakdown": breakdown,
        "delta_this_month": compute_delta_this_month(),
        "trend": compute_trend(period),
        "milestone": compute_milestone_projection(),
        "accounts": compute_accounts_hierarchy(),
        "bucket_labels": BUCKET_LABELS,
    }
