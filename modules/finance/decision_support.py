"""Decision support — sizing, rebalancing, tax-loss harvesting, alerts.

Phase 15c, Category F. The actionable layer: it turns the 15a/15b analytics into
specific suggestions David can act on, enforcing the rules in
``Investment_Philosophy.md`` (Sections 0, 17, 18) as literal gates.

The pure-calculation functions (``suggested_position_size``,
``bucket_allocations``, ``rebalance_recommendations``, ``harvest_candidates``,
``concentration_alerts``) take plain ``positions`` (list of dicts with
``ticker`` / ``quantity`` / ``bucket`` / ``type``) and a ``prices`` dict so they
stay easy to unit-test. :func:`current_positions_and_prices` assembles those from
the live holdings + price cache, and the ``backend/api/finance/decisions.py``
endpoints are thin wrappers over both.

NOTE on the conviction → size gates: Investment Philosophy Section 7.1 (the
5-Layer Research Framework + 6-Point Conviction Scorecard) was not yet locked
when this was built, so ``CONVICTION_TO_SIZE`` below encodes David's v3 working
defaults. When Section 7.1 is finalized, swap the mapping here — it is the single
source of truth the rest of the layer reads.
"""
from __future__ import annotations

from datetime import date, timedelta

from modules.finance.positions import (
    cost_basis,
    current_holdings,
    get_position,
    open_lots,
    transactions_for,
)
from modules.finance.price_history import latest_price


# ============================================================
# Position sizing (per Investment_Philosophy.md Section 17)
# ============================================================

# v3 working default until Section 7.1 is locked — see module docstring.
CONVICTION_TO_SIZE = {
    6: 0.05,    # 5% max
    5: 0.04,
    4: 0.025,
    3: 0.015,   # 1.5% minimum entry
    2: 0.0,     # No entry
    1: 0.0,
    0: 0.0,
}


def suggested_position_size(conviction_score: int, portfolio_value: float) -> dict:
    """Map conviction score to position size + EUR amount."""
    weight = CONVICTION_TO_SIZE.get(conviction_score, 0)
    return {
        "conviction_score": conviction_score,
        "weight_pct": weight * 100,
        "eur_amount": weight * portfolio_value,
        "can_enter": weight > 0,
        "rationale": f"Conviction {conviction_score}/6 maps to {weight*100:.1f}% per Investment Philosophy Section 17",
    }


# ============================================================
# Rebalance suggestor (per Section 18 cross-bucket rebalancing)
# ============================================================

BUCKET_TARGETS = {
    "etf_foundation": 0.49,
    "single_stocks": 0.21,
    "crypto": 0.24,
    "wild_cards": 0.06,
}
BUCKET_DRIFT_TOLERANCE = 0.04  # ±4 percentage points before triggering rebalance


def bucket_allocations(positions: list, prices: dict) -> dict:
    """Compute current allocation per bucket."""
    bucket_values = {b: 0.0 for b in BUCKET_TARGETS}
    for p in positions:
        bucket = p.get("bucket", "single_stocks")
        qty = p.get("quantity", 0)
        price = prices.get(p["ticker"], 0)
        if bucket not in bucket_values:
            bucket = "single_stocks"
        bucket_values[bucket] += qty * price
    total = sum(bucket_values.values())
    if total == 0:
        return {b: {"value": 0, "weight": 0, "target": t, "drift": -t} for b, t in BUCKET_TARGETS.items()}
    return {
        b: {
            "value": bucket_values[b],
            "weight": bucket_values[b] / total,
            "target": BUCKET_TARGETS[b],
            "drift": bucket_values[b] / total - BUCKET_TARGETS[b],
        }
        for b in BUCKET_TARGETS
    }


def rebalance_recommendations(allocations: dict, portfolio_value: float) -> list[dict]:
    """Generate rebalancing trade suggestions to bring allocations within tolerance."""
    recs = []
    for bucket, alloc in allocations.items():
        drift = alloc["drift"]
        if abs(drift) > BUCKET_DRIFT_TOLERANCE:
            target_value = alloc["target"] * portfolio_value
            current_value = alloc["value"]
            delta = target_value - current_value
            action = "buy" if delta > 0 else "sell"
            recs.append({
                "bucket": bucket,
                "action": action,
                "current_weight": alloc["weight"],
                "target_weight": alloc["target"],
                "drift_pct": drift * 100,
                "delta_eur": delta,
                "priority": "high" if abs(drift) > 0.06 else "medium",
                "rationale": f"{bucket} at {alloc['weight']*100:.1f}% vs target {alloc['target']*100:.0f}% — {'trim' if delta < 0 else 'add'} €{abs(delta):,.0f}",
            })
    # Special rule: crypto > 30% → forced trim to 24% with proceeds to ETF (per Section 0.3)
    if allocations.get("crypto", {}).get("weight", 0) > 0.30:
        recs.insert(0, {
            "bucket": "crypto",
            "action": "trim_to_target",
            "rationale": "Crypto sleeve exceeded 30% trigger — trim to 24%, proceeds go to ETF Foundation (never recycled into crypto)",
            "priority": "high",
            "delta_eur": (allocations["crypto"]["weight"] - 0.24) * portfolio_value,
        })
    return recs


# ============================================================
# Tax-loss harvesting (German Spekulationsfrist)
# ============================================================

def harvest_candidates(positions: list, prices: dict, today: date | None = None) -> list[dict]:
    """Identify positions at a loss that could be sold for tax purposes.

    German rules:
    - Equities: gains taxed via Abgeltungsteuer (~26.4%); losses offset gains
    - Crypto: holding > 12 months = tax-free (Spekulationsfrist). Don't harvest crypto < 12 months unless intentional.
    - Sparerpauschbetrag: €1,000/year tax-free for equity gains
    """
    today = today or date.today()
    candidates = []
    for p in positions:
        ticker = p["ticker"]
        qty = p["quantity"]
        avg_cost, _ = cost_basis(ticker)
        current_price = prices.get(ticker, 0)
        if not avg_cost or not current_price:
            continue
        unrealized_pnl = (current_price - avg_cost) * qty
        unrealized_pnl_pct = (current_price - avg_cost) / avg_cost

        if unrealized_pnl < 0:
            # Check holding period. ``transactions_for`` returns Transaction
            # objects (pydantic), so use attribute access, not subscripting.
            txs = transactions_for(ticker)
            earliest_buy = min((t.date for t in txs if t.action == "buy"), default=today)
            holding_days = (today - earliest_buy).days

            crypto = p.get("type") == "crypto"

            # For crypto: only harvest if < 12 months (otherwise gain would be tax-free anyway)
            # For equities: always candidate when at loss
            should_consider = True
            if crypto and holding_days < 365:
                # Loss can offset other crypto gains, but holding to 365d for tax-free gain might be better strategy
                should_consider = True
            elif crypto and holding_days >= 365:
                # If sold at gain, would be tax-free — losses here don't help tax-wise
                should_consider = False

            if should_consider:
                candidates.append({
                    "ticker": ticker,
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_pnl_pct": unrealized_pnl_pct * 100,
                    "holding_days": holding_days,
                    "type": p.get("type"),
                    "tax_savings_estimate": abs(unrealized_pnl) * 0.264 if not crypto else abs(unrealized_pnl) * 0.42,  # rough
                    "warning": "Crypto loss — but consider holding to 12 months for tax-free gain potential" if crypto else None,
                })
    return sorted(candidates, key=lambda x: x["unrealized_pnl"])


# ============================================================
# Concentration + drift alerts
# ============================================================

def concentration_alerts(positions: list, prices: dict) -> list[dict]:
    """Alert if any position exceeds Section 0.2 max position (5% in Single Stocks)
    or if bucket cap exceeded."""
    alerts = []
    total = sum(p["quantity"] * prices.get(p["ticker"], 0) for p in positions)
    if total == 0:
        return []

    # Per-position check
    for p in positions:
        value = p["quantity"] * prices.get(p["ticker"], 0)
        weight = value / total
        bucket = p.get("bucket", "single_stocks")

        if bucket == "single_stocks":
            if weight > 0.07:  # 7% drift trigger per Section 0.2
                alerts.append({
                    "type": "drift_trigger",
                    "ticker": p["ticker"],
                    "weight": weight,
                    "rationale": f"{p['ticker']} at {weight*100:.1f}% — Section 0.2 says trim to 5% when above 7%",
                    "severity": "high",
                })
            elif weight > 0.05:
                alerts.append({
                    "type": "approaching_max",
                    "ticker": p["ticker"],
                    "weight": weight,
                    "rationale": f"{p['ticker']} at {weight*100:.1f}% — max single position is 5%",
                    "severity": "medium",
                })
        elif bucket == "crypto":
            if weight > 0.08:  # Per Section 0.3, max 8% per crypto position
                alerts.append({
                    "type": "crypto_position_cap",
                    "ticker": p["ticker"],
                    "weight": weight,
                    "rationale": f"{p['ticker']} at {weight*100:.1f}% — Section 0.3 caps each crypto at 8%",
                    "severity": "high",
                })
        elif bucket == "wild_cards":
            if weight > 0.02:
                alerts.append({
                    "type": "wild_card_position_cap",
                    "ticker": p["ticker"],
                    "weight": weight,
                    "rationale": f"{p['ticker']} at {weight*100:.1f}% — Section 0.4 caps each wild card at 2%",
                    "severity": "high",
                })

    return alerts


# ============================================================
# Quarterly cadence (Chunk 7, D7) — a review alert regardless of drift
# ============================================================

QUARTER_START_MONTHS = (1, 4, 7, 10)
QUARTERLY_WINDOW_DAYS = 7  # the alert is live for the first 7 calendar days of the quarter


def quarterly_cadence_alert(as_of: date | None = None) -> dict | None:
    """The "quarterly_review" alert when ``as_of`` is within 7 days of Jan/Apr/Jul/Oct 1.

    Live on days 1-7 of those months (1 Jan through 7 Jan, ...) and silent otherwise,
    independent of drift — it sits alongside the ±4pp drift trigger, it doesn't replace it.
    """
    as_of = as_of or date.today()
    if as_of.month not in QUARTER_START_MONTHS or as_of.day > QUARTERLY_WINDOW_DAYS:
        return None
    quarter = f"Q{(as_of.month - 1) // 3 + 1} {as_of.year}"
    start = date(as_of.year, as_of.month, 1)
    return {
        "type": "quarterly_review",
        "quarter": quarter,
        "due_date": start.isoformat(),
        "window_ends": (start + timedelta(days=QUARTERLY_WINDOW_DAYS - 1)).isoformat(),
        "severity": "medium",
        "rationale": f"{quarter} rebalance review due — even without drift, review positions per your quarterly cadence",
    }


def decision_alerts(positions: list, prices: dict, as_of: date | None = None) -> list[dict]:
    """The full alert list: per-position cap/drift alerts plus the quarterly review (if due)."""
    alerts = concentration_alerts(positions, prices)
    quarterly = quarterly_cadence_alert(as_of)
    return [quarterly, *alerts] if quarterly else alerts


# ============================================================
# Security-level rebalance (Chunk 7, D6) — bucket recs -> specific trades
# ============================================================

BUCKET_LABELS = {
    "etf_foundation": "ETF Foundation",
    "single_stocks": "Single Stocks",
    "crypto": "Crypto",
    "wild_cards": "Wild Cards",
}

# How to choose which crypto to sell inside an over-allocated crypto bucket:
#   "youngest_first"  — shortest holding period first (the Chunk 7 brief as written)
#   "tax_free_first"  — positions already past the 365-day Spekulationsfrist first
# NB: these pull in opposite directions tax-wise. Selling coins held < 365 days realizes
# *taxable* gains; coins held >= 365 days are tax-free (§23 EStG), which is why
# harvest_candidates() above treats them the opposite way. The brief's rule is the
# default; every trade carries an explicit tax note so the consequence is on the page,
# and this constant is the one-line switch.
CRYPTO_SELL_ORDER = "youngest_first"

ABGELTUNG_TEXT = "Abgeltungsteuer applies"


def _lot_days(lot: dict, today: date) -> int:
    return (today - lot["date"]).days


def sale_tax_note(ticker: str, ptype: str | None, units: float, today: date, lots: list[dict]) -> str:
    """One-line German tax note for selling ``units`` of ``ticker`` (FIFO, oldest lots first).

    Stocks/ETFs: Abgeltungsteuer applies whatever the holding period. Crypto: gains on
    units held >= 365 days are tax-free (Spekulationsfrist met); younger units are taxable,
    and the note says when they'd turn tax-free. Mixed sales are split by lot.
    """
    if not lots or units <= 0:
        return f"{ABGELTUNG_TEXT}" if ptype != "crypto" else "no buy history found — holding period unknown"
    remaining, consumed = units, []
    for lot in lots:  # oldest first
        take = min(lot["quantity"], remaining)
        consumed.append((lot, take))
        remaining -= take
        if remaining <= 1e-9:
            break
    oldest_days = _lot_days(consumed[0][0], today)
    if ptype != "crypto":
        return f"Held {oldest_days} days — {ABGELTUNG_TEXT}"

    free = sum(q for lot, q in consumed if _lot_days(lot, today) >= 365)
    taxable_lots = [(lot, q) for lot, q in consumed if _lot_days(lot, today) < 365]
    taxable = sum(q for _, q in taxable_lots)
    if not taxable_lots:
        return f"Held {oldest_days} days — Spekulationsfrist met (crypto only), gains tax-free"
    youngest = min(_lot_days(lot, today) for lot, _ in taxable_lots)
    days_left = min(365 - _lot_days(lot, today) for lot, _ in taxable_lots)
    if free <= 1e-9:
        return (f"Held {youngest} days — inside the Spekulationsfrist, gains taxable "
                f"(tax-free in {days_left} days)")
    return (f"{free:.4g} units held 365+ days (tax-free), {taxable:.4g} units inside the "
            f"Spekulationsfrist (taxable; youngest {youngest} days)")


def _sell_order(candidates: list[dict], ptype_bucket: str) -> list[dict]:
    """Sort sell candidates. Crypto: by holding period (see CRYPTO_SELL_ORDER); everything
    else: largest unrealized gain first. Ties -> larger weight (concentration) first."""
    if ptype_bucket == "crypto":
        sign = 1 if CRYPTO_SELL_ORDER == "youngest_first" else -1
        return sorted(candidates, key=lambda c: (sign * c["age_days"], -c["weight"], c["ticker"]))
    return sorted(candidates, key=lambda c: (-c["unrealized"], -c["weight"], c["ticker"]))


def primary_ticker_for_bucket(bucket: str) -> str | None:
    """The bucket's default buy: the first ticker listed for it in config/ticker_buckets.yaml."""
    from modules.finance.buckets import _load_ticker_bucket_map

    for t, b in _load_ticker_bucket_map().items():
        if b == bucket:
            return t
    return None


def security_level_rebalance(
    positions: list,
    prices: dict,
    recommendations: list[dict],
    portfolio_value_: float,
    today: date | None = None,
    lots_fn=None,
) -> list[dict]:
    """Turn bucket-level rebalance recs into specific security trades.

    Sells come out of each over-allocated bucket (order: see :func:`_sell_order`), buys go
    into each under-allocated bucket — to the holding furthest below its equal-weight
    share of the bucket first, else the bucket's primary ticker. A crypto trim's proceeds
    go to the ETF Foundation (Section 0.3). Amounts are in the same valuation basis as the
    bucket recs (cached native prices), so ``units = eur_amount / price``.

    Returns ``[{action, ticker, units, eur_amount, bucket, reason, tax_note, text}]``;
    sells first. Empty when no bucket is outside tolerance.
    """
    today = today or date.today()
    lots_fn = lots_fn or open_lots
    if not recommendations or portfolio_value_ <= 0:
        return []

    sell_eur: dict[str, float] = {}
    buy_eur: dict[str, float] = {}
    for r in recommendations:
        b = r.get("bucket")
        if r["action"] in ("sell", "trim_to_target"):
            amt = abs(r["delta_eur"])
            sell_eur[b] = max(sell_eur.get(b, 0.0), amt)  # trim_to_target and sell are the same amount
        elif r["action"] == "buy":
            buy_eur[b] = buy_eur.get(b, 0.0) + r["delta_eur"]

    # Section 0.3: a crypto trim's proceeds go to ETF Foundation, never back into crypto.
    surplus = sum(sell_eur.values()) - sum(buy_eur.values())
    proceeds_to_etf = 0.0
    if sell_eur.get("crypto") and surplus > 1e-6:
        proceeds_to_etf = surplus
        buy_eur["etf_foundation"] = buy_eur.get("etf_foundation", 0.0) + surplus

    by_ticker = {p["ticker"]: p for p in positions}
    value = {t: p["quantity"] * prices.get(t, 0.0) for t, p in by_ticker.items()}
    total = sum(value.values()) or 1.0
    trades: list[dict] = []

    # --- sells -------------------------------------------------------------------------
    for bucket, need in sell_eur.items():
        cands = []
        for t, p in by_ticker.items():
            price = prices.get(t, 0.0)
            if p.get("bucket") != bucket or price <= 0 or p["quantity"] <= 0:
                continue
            lots = lots_fn(t)
            avg_cost, _ = cost_basis(t)
            cands.append({
                "ticker": t, "type": p.get("type"), "price": price, "quantity": p["quantity"],
                "weight": value[t] / total, "lots": lots,
                "age_days": _lot_days(lots[0], today) if lots else 0,
                "unrealized": (price - avg_cost) * p["quantity"] if avg_cost else 0.0,
            })
        remaining = need
        for c in _sell_order(cands, bucket):
            if remaining <= 0.5:
                break
            eur = min(remaining, c["price"] * c["quantity"])
            units = round(eur / c["price"], 4)
            remaining -= eur
            label = BUCKET_LABELS.get(bucket, bucket)
            trades.append({
                "action": "sell", "ticker": c["ticker"], "units": units, "eur_amount": round(eur, 2),
                "bucket": bucket, "reason": f"{label} over by €{need:,.0f}",
                "tax_note": sale_tax_note(c["ticker"], c["type"], units, today, c["lots"]),
            })

    # --- buys --------------------------------------------------------------------------
    for bucket, need in buy_eur.items():
        held = [(t, value[t]) for t, p in by_ticker.items() if p.get("bucket") == bucket and prices.get(t, 0) > 0]
        target_each = (BUCKET_TARGETS.get(bucket, 0.0) * portfolio_value_ / len(held)) if held else 0.0
        order = sorted(((t, max(0.0, target_each - v)) for t, v in held), key=lambda x: (-x[1], x[0]))
        remaining = need
        plan: list[tuple[str, float]] = []
        for t, shortfall in order:
            if remaining <= 0.5:
                break
            amt = min(remaining, shortfall) if shortfall > 0 else 0.0
            if amt > 0:
                plan.append((t, amt))
                remaining -= amt
        if remaining > 0.5:  # nothing under its equal-weight share (or no holdings): top up the first / primary
            target = order[0][0] if order else primary_ticker_for_bucket(bucket)
            if target:
                plan.append((target, remaining))
        label = BUCKET_LABELS.get(bucket, bucket)
        merged: dict[str, float] = {}  # shortfall fill + leftover top-up may hit the same ticker
        for t, amt in plan:
            merged[t] = merged.get(t, 0.0) + amt
        for t, amt in merged.items():
            price = prices.get(t) or _fallback_price(t)
            if not price:
                continue
            reason = f"{label} under by €{need:,.0f}"
            if bucket == "etf_foundation" and proceeds_to_etf > 0:
                reason = f"crypto trim proceeds → {label} (Section 0.3)"
            trades.append({
                "action": "buy", "ticker": t, "units": round(amt / price, 4), "eur_amount": round(amt, 2),
                "bucket": bucket, "reason": reason, "tax_note": "no tax on a purchase",
            })

    for tr in trades:
        verb = "Sell" if tr["action"] == "sell" else "Buy"
        tr["text"] = f"{verb} {tr['units']:g} units {tr['ticker']} ({tr['reason']})"
    return trades


def _fallback_price(ticker: str) -> float | None:
    """Price for a buy target that isn't held yet (the bucket's primary ticker)."""
    return latest_price(ticker)


# ============================================================
# Hypothesis-conviction-weighted views
# ============================================================

def conviction_weighted_view() -> dict:
    """Read hypothesis tracker, weight portfolio analysis by conviction levels."""
    from modules.finance.optimization import hypotheses_as_views
    views = hypotheses_as_views()
    # Calculate aggregate conviction-weighted expected return
    total_confidence = sum(v["confidence"] for v in views)
    if total_confidence == 0:
        return {"views": [], "aggregate_expected_return": None, "n_views": 0}
    weighted_return = sum(v["expected_return"] * v["confidence"] for v in views) / total_confidence
    return {
        "views": views,
        "aggregate_expected_return": weighted_return,
        "n_views": len(views),
    }


# ============================================================
# Live-state assembly (used by the API layer)
# ============================================================

def current_positions_and_prices() -> tuple[list[dict], dict[str, float]]:
    """Assemble the pure-function inputs from live holdings + the price cache.

    ``positions`` is a list of ``{ticker, quantity, bucket, type}`` dicts.
    ``bucket`` goes through the same override/map resolution as the Bucket
    Allocation panel (Chunk 2.5's buckets.resolve_bucket) rather than a blind
    "single_stocks" guess, so e.g. a crypto ticker only known via the seed map
    now gets checked against the crypto cap here too, not the equity one. A
    truly unresolvable ticker (no override, not in the map) still falls back
    to "single_stocks" rather than "unassigned" — concentration_alerts() has
    no "unassigned" branch, and the point of that fallback is that nothing
    silently skips the checks just for lacking a bucket.
    """
    from modules.finance.buckets import resolve_bucket

    holdings = current_holdings()
    positions: list[dict] = []
    prices: dict[str, float] = {}
    for ticker, qty in holdings.items():
        meta = get_position(ticker)
        prices[ticker] = latest_price(ticker) or 0.0
        bucket = resolve_bucket(ticker)
        if bucket not in BUCKET_TARGETS:  # "unassigned" -> safe, checked-anyway default
            bucket = "single_stocks"
        positions.append({
            "ticker": ticker,
            "quantity": qty,
            "bucket": bucket,
            "type": meta.type if meta else None,
        })
    return positions, prices


def portfolio_value(positions: list, prices: dict) -> float:
    """Total market value of the supplied positions at the supplied prices."""
    return sum(p["quantity"] * prices.get(p["ticker"], 0) for p in positions)


def decision_summary(as_of: date | None = None) -> dict:
    """Bundle counts + headline figures for the Home 'decision alerts' panel.

    A due quarterly review counts as one more rebalance item (it is a rebalance-review
    alert); the alert itself rides along under ``quarterly_review``.
    """
    positions, prices = current_positions_and_prices()
    pv = portfolio_value(positions, prices)
    allocations = bucket_allocations(positions, prices)
    rebal = rebalance_recommendations(allocations, pv)
    harvest = harvest_candidates(positions, prices)
    alerts = concentration_alerts(positions, prices)
    quarterly = quarterly_cadence_alert(as_of)
    return {
        "portfolio_value": pv,
        "quarterly_review": quarterly,
        "rebalance_count": len(rebal) + (1 if quarterly else 0),
        "rebalance_high": sum(1 for r in rebal if r.get("priority") == "high"),
        "concentration_count": len(alerts),
        "concentration_high": sum(1 for a in alerts if a.get("severity") == "high"),
        "harvest_count": len(harvest),
        "harvest_savings": sum(c["tax_savings_estimate"] for c in harvest),
    }
