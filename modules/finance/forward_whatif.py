"""Forward EUR what-if simulator (Chunk 7, D5).

"What happens to my portfolio if I buy/sell €X of TICKER?" — distinct from the Watchlist
tab's %-weight "Simulate Add to Portfolio". It re-runs the live holdings with the trade
applied and reports, current vs projected:

* bucket allocation and drift vs the 49/21/24/6 targets (with per-bucket deltas),
* Sharpe / Sortino / volatility,
* which bucket a bought ticker maps to (``buckets.resolve_bucket`` — override, then the
  seed map, then "unassigned", which is *analysed* as Single Stocks like everywhere else),
* warnings: buckets pushed outside the ±4pp band (and the Section 0.3 hard triggers —
  crypto > 30 %, ETF < 45 %), per-position caps (Sections 0.2-0.4), and a single-position
  concentration limit (:data:`MAX_SINGLE_POSITION`).

**Risk numbers.** ``sharpe_capm`` is forward-looking and *benchmark-dependent*: expected
return w·mu with mu = CAPM against the selected benchmark (:func:`optimization.mu_cov`,
the same vector as the Optimization tab, 4 % rf) over the sample covariance — so it moves
with the shared benchmark selection. ``sharpe_historical`` / ``sortino`` / ``vol`` are
realized figures from the static-weight portfolio return series (:mod:`risk`), which do
not depend on a benchmark.

**Valuation basis.** Like the rest of the allocation code, holdings are valued at cached
native-currency prices; the trade's EUR amount is converted to units with the ticker's
own FX rate to EUR. Cross-currency FX effects on weights are ignored (same as the
Bucket Allocation panel).
"""
from __future__ import annotations

import math
import re
from typing import Optional

import numpy as np

from core.config import BENCHMARKS, DEFAULT_BENCHMARK, DEFAULT_RISK_FREE_RATE, get_logger
from modules.finance import decision_support as ds
from modules.finance import risk
from modules.finance.buckets import resolve_bucket_with_source
from modules.finance.optimization import mu_cov
from modules.finance.performance import portfolio_returns
from modules.finance.positions import current_holdings, get_position
from modules.finance.price_history import fx_rate_to_eur, latest_price, quote_currency

logger = get_logger(__name__)

MAX_SINGLE_POSITION = 0.10  # "top-1 > 10%" concentration limit from the brief
# A 45-50% ETF core would trip a literal top-1 > 10% test permanently, so the ETF
# Foundation bucket is exempt from the single-position check (its own floor is Section 0's).
CONCENTRATION_EXEMPT_BUCKETS = ("etf_foundation",)
CRYPTO_TRIGGER = 0.30   # Section 0.3: crypto above this forces a trim
ETF_FLOOR = 0.45        # Section 0: ETF Foundation below this triggers a rebalance

_TICKER_OK = re.compile(r"^[A-Z0-9][A-Z0-9.\-^=]{0,14}$")


class WhatIfError(ValueError):
    """A trade that can't be simulated (unowned sell, no price, bad input)."""


def native_to_eur(ticker: str) -> tuple[float, bool]:
    """``(rate, assumed)`` — native-currency -> EUR for ``ticker``; ``assumed`` = the rate
    couldn't be fetched and 1.0 was used."""
    try:
        ccy = quote_currency(ticker).upper()
        if ccy == "EUR":
            return 1.0, False
        rate, _ = fx_rate_to_eur(ccy)
        return (float(rate), False) if rate else (1.0, True)
    except Exception as exc:  # noqa: BLE001 — never let an FX hiccup kill a simulation
        logger.info("FX lookup failed for %s: %s", ticker, exc)
        return 1.0, True


def _positions_for(holdings: dict[str, float]) -> list[dict]:
    """Positions in the shape decision_support's pure functions take. An unassigned
    bucket is analysed as Single Stocks (same fallback current_positions_and_prices uses)."""
    out = []
    for t, q in holdings.items():
        bucket, _ = resolve_bucket_with_source(t)
        if bucket not in ds.BUCKET_TARGETS:
            bucket = "single_stocks"
        meta = get_position(t)
        ptype = meta.type if meta else ("crypto" if t.upper().endswith(("-USD", "-EUR", "-GBP")) else "equity")
        out.append({"ticker": t, "quantity": q, "bucket": bucket, "type": ptype})
    return out


def _risk_metrics(holdings: dict[str, float], prices: dict[str, float], benchmark_ticker: str) -> dict:
    """Sharpe (CAPM, forward), Sharpe / Sortino / vol (historical) for a holdings dict."""
    empty = {"sharpe_capm": None, "sharpe_historical": None, "sortino": None, "vol": None}
    if not holdings:
        return empty
    rets = portfolio_returns(holdings)
    out = dict(empty)
    if not rets.empty:
        out.update(sharpe_historical=risk.sharpe(rets), sortino=risk.sortino(rets), vol=risk.annualized_vol(rets))

    tickers = list(holdings)
    mu, S = mu_cov(tickers, benchmark_ticker)
    if not mu.empty:
        mv = {t: holdings[t] * (prices.get(t) or 0.0) for t in mu.index}
        total = sum(mv.values())
        if total > 0:
            w = np.array([mv[t] / total for t in mu.index])
            ret = float(w @ mu.values)
            vol = float(math.sqrt(max(w @ S.values @ w, 0.0)))
            out["sharpe_capm"] = (ret - DEFAULT_RISK_FREE_RATE) / vol if vol else None
    return out


def _delta(cur: Optional[float], new: Optional[float]) -> dict:
    return {"current": cur, "projected": new, "delta": (new - cur) if cur is not None and new is not None else None}


def simulate_forward_trade(
    ticker: str,
    action: str,
    eur_amount: float,
    benchmark: str = DEFAULT_BENCHMARK,
) -> dict:
    """Simulate buying or selling ``eur_amount`` EUR of ``ticker`` (see module docstring).

    Raises :class:`WhatIfError` for input that can't be simulated: bad ticker/action/
    amount, no price data, or selling something you don't hold. Selling more than the
    position is worth is capped at the whole position (``capped: true``).
    """
    action = (action or "").lower()
    ticker = (ticker or "").strip().upper()
    if action not in ("buy", "sell"):
        raise WhatIfError("action must be 'buy' or 'sell'")
    if not _TICKER_OK.match(ticker):
        raise WhatIfError("enter a valid ticker symbol")
    if not eur_amount or eur_amount <= 0:
        raise WhatIfError("amount must be a positive EUR figure")

    holdings = {t: q for t, q in current_holdings().items()}
    key = next((k for k in holdings if k.upper() == ticker), None)
    held = holdings.get(key, 0.0) if key else 0.0
    if action == "sell" and held <= 0:
        raise WhatIfError(f"you don't hold {ticker} — there is nothing to sell")

    price = latest_price(key or ticker)
    if not price:
        raise WhatIfError(f"no price data for {ticker}")
    fx, fx_assumed = native_to_eur(key or ticker)
    price_eur = price * fx
    units = eur_amount / price_eur
    capped = False
    if action == "sell" and units > held:
        units, capped = held, True
    eur_effective = units * price_eur

    tk = key or ticker
    projected = dict(holdings)
    projected[tk] = held + units if action == "buy" else held - units
    if projected[tk] <= 1e-9:
        projected.pop(tk)

    prices = {t: (latest_price(t) or 0.0) for t in {*holdings, *projected}}
    bench_ticker = BENCHMARKS.get(benchmark, BENCHMARKS[DEFAULT_BENCHMARK])["ticker"]

    pos_now, pos_new = _positions_for(holdings), _positions_for(projected)
    alloc_now = ds.bucket_allocations(pos_now, prices)
    alloc_new = ds.bucket_allocations(pos_new, prices)
    pv_now, pv_new = ds.portfolio_value(pos_now, prices), ds.portfolio_value(pos_new, prices)
    tol = ds.BUCKET_DRIFT_TOLERANCE

    bucket_table, band_breaches = [], []
    for b, target in ds.BUCKET_TARGETS.items():
        a0, a1 = alloc_now[b], alloc_new[b]
        row = {
            "bucket": b, "label": ds.BUCKET_LABELS[b], "target": target,
            "current_weight": a0["weight"], "projected_weight": a1["weight"],
            "weight_delta": a1["weight"] - a0["weight"],
            "current_drift": a0["drift"], "projected_drift": a1["drift"],
            "drift_delta": a1["drift"] - a0["drift"],
            "current_value": a0["value"], "projected_value": a1["value"],
        }
        bucket_table.append(row)
        if pv_now > 0 and pv_new > 0 and abs(a1["drift"]) > tol:
            band_breaches.append({
                "bucket": b, "label": row["label"], "projected_weight": a1["weight"], "target": target,
                "projected_drift": a1["drift"], "before_drift": a0["drift"],
                "new": abs(a0["drift"]) <= tol,
                "worsened": abs(a1["drift"]) > abs(a0["drift"]) + 1e-9,
            })

    hard = []
    if pv_now > 0 and pv_new > 0:  # against an empty portfolio every first buy trivially breaches
        if alloc_new["crypto"]["weight"] > CRYPTO_TRIGGER:
            hard.append({"bucket": "crypto", "rule": f"crypto above the {CRYPTO_TRIGGER:.0%} trigger (Section 0.3) — forces a trim to 24%",
                         "weight": alloc_new["crypto"]["weight"]})
        if alloc_new["etf_foundation"]["weight"] < ETF_FLOOR:
            hard.append({"bucket": "etf_foundation", "rule": f"ETF Foundation below the {ETF_FLOOR:.0%} floor — rebalance trigger",
                         "weight": alloc_new["etf_foundation"]["weight"]})

    # per-position caps (Sections 0.2-0.4) — only those touching the traded ticker
    cap_alerts = [a for a in ds.concentration_alerts(pos_new, prices) if a["ticker"].upper() == ticker]

    weights = {p["ticker"]: p["quantity"] * prices.get(p["ticker"], 0) / pv_new for p in pos_new} if pv_new > 0 else {}
    bucket_of = {p["ticker"]: p["bucket"] for p in pos_new}
    checked = {t: w for t, w in weights.items() if bucket_of[t] not in CONCENTRATION_EXEMPT_BUCKETS}
    top1 = max(weights.items(), key=lambda kv: kv[1]) if weights else None
    concentration = [
        {"ticker": t, "weight": w, "limit": MAX_SINGLE_POSITION}
        for t, w in sorted(checked.items(), key=lambda kv: -kv[1]) if w > MAX_SINGLE_POSITION
    ]

    m_now = _risk_metrics(holdings, prices, bench_ticker)
    m_new = _risk_metrics(projected, prices, bench_ticker)
    metrics = {k: _delta(m_now[k], m_new[k]) for k in m_now}

    bucket, source = resolve_bucket_with_source(tk)
    warnings: list[str] = []
    if pv_now <= 0:
        warnings.append("your portfolio is empty — bucket-allocation warnings are skipped (any first buy would breach every band)")
    if capped:
        warnings.append(f"selling €{eur_amount:,.0f} exceeds the position — capped at the whole holding (≈€{eur_effective:,.0f})")
    if fx_assumed:
        warnings.append("EUR conversion rate unavailable — treated the price as EUR")
    if bucket == "unassigned":
        warnings.append(f"{ticker} has no bucket yet — analysed as Single Stocks; assign one on the Holdings tab")
    for h in hard:
        warnings.append(h["rule"])
    for br in band_breaches:
        if br["new"] or br["worsened"]:
            warnings.append(f"{br['label']} would be {br['projected_weight']:.1%} vs {br['target']:.0%} target ({br['projected_drift'] * 100:+.1f}pp, outside ±{tol * 100:.0f}pp)")
    for a in cap_alerts:
        warnings.append(a["rationale"])
    for c in concentration:
        if c["ticker"].upper() == ticker:
            warnings.append(f"{c['ticker']} would be {c['weight']:.1%} of the portfolio — above the {MAX_SINGLE_POSITION:.0%} single-position limit")

    return {
        "ticker": ticker,
        "action": action,
        "eur_amount": eur_amount,
        "eur_effective": eur_effective,
        "units": units,
        "price_native": price,
        "price_eur": price_eur,
        "fx_assumed": fx_assumed,
        "capped": capped,
        "benchmark": benchmark,
        "bucket": {"bucket": bucket, "label": ds.BUCKET_LABELS.get(bucket, "Unassigned"), "source": source},
        "portfolio_value": {"current": pv_now, "projected": pv_new},
        "bucket_table": bucket_table,
        "metrics": metrics,
        "projected_holdings": projected,
        "bucket_band_breaches": band_breaches,
        "hard_cap_breaches": hard,
        "position_cap_alerts": cap_alerts,
        "concentration_breaches": concentration,
        "top1": {"ticker": top1[0], "weight": top1[1]} if top1 else None,
        "warnings": warnings,
    }
