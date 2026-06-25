"""The nine research skills (Phase C).

Each is a :class:`~modules.agents.skills.research.engine.ResearchSkill`: an
analyst persona, the required Markdown report outline, and a sidecar schema
(given by example). All share the same output contract — ``.docx`` deep-dive +
``.json`` sidecar — produced by :func:`engine.generate`.

``stock_analysis`` carries the EXACT sidecar schema locked in the v3 build spec
(§ d). The other eight reuse the same base keys (recommendation, fair-value
range, thesis one-liner, scenarios, monitorables, thesis-break triggers,
catalysts) so the dashboard's report reader treats every report uniformly,
plus skill-specific extras.
"""
from __future__ import annotations

from modules.agents.skills.research.engine import ResearchSkill, generate

# Reusable scenario block (bull/base/bear) for the sidecar examples.
_SCENARIOS = {
    "bull": {"prob": 0.30, "implied_value": 0, "note": "<driver>"},
    "base": {"prob": 0.50, "implied_value": 0, "note": "<driver>"},
    "bear": {"prob": 0.20, "implied_value": 0, "note": "<driver>"},
}

# --- the canonical equity report (exact v3-spec sidecar) ---------------------
STOCK_ANALYSIS = ResearchSkill(
    key="stock_analysis",
    label="Stock Analysis",
    target_kind="ticker",
    persona=(
        "You are a buy-side senior equity analyst writing a full deep-dive equity "
        "research report for a sophisticated investor (M&A/finance background)."
    ),
    outline="""# <Company> (<TICKER>) — Equity Research
**Title block:** company, ticker, exchange, current price, market cap, date, recommendation.

## 1. Executive summary
## 2. Business & model — how it makes money
## 3. Industry & competitive position (moat)
## 4. Financials — growth, margins, returns, balance sheet
## 5. Capital allocation
## 6. Management & governance
## 7. Bull case
## 8. Bear case
## 9. Valuation — DCF (state assumptions + WACC + terminal)
## 10. Reverse-DCF — what the current price implies
## 11. Scenarios — bull / base / bear (probability + implied value)
## 12. Recommendation, fair-value range, monitorables, thesis-break triggers, catalysts (incl. next earnings date)""",
    sidecar_example={
        "ticker": "BABA", "company": "Alibaba", "exchange": "NYSE",
        "analysis_date": "2026-06-18", "currency": "EUR",
        "current_price_at_analysis": 78.40, "market_cap": "...",
        "horizon": "mid (1-3yr)",
        "recommendation": "Accumulate",
        "fair_value_low": 95, "fair_value_high": 120,
        "upside_low_pct": 21, "upside_high_pct": 53,
        "thesis_oneliner": "Cloud + AI optionality underpriced; weakness is regulatory/macro beta.",
        "scenarios": {
            "bull": {"prob": 0.35, "implied_value": 140, "note": "cloud reaccel + buyback"},
            "base": {"prob": 0.45, "implied_value": 108, "note": "steady CMR, GMV flat"},
            "bear": {"prob": 0.20, "implied_value": 60, "note": "regulatory regime shift"},
        },
        "monitorables": ["cloud growth", "CMR take-rate", "buyback pace", "reg headlines"],
        "thesis_break_triggers": ["cloud growth <10% two quarters", "new data-localization regime", "buyback paused"],
        "catalysts": [{"label": "Q1 earnings", "date": "2026-08-14"}, {"label": "cloud spinoff decision"}],
        "report_path": "4_Areas/Investing/Stock_Reports/BABA/2026-06-18_BABA.docx",
        "sources_as_of": "2026-06-18",
    },
)

# --- the eight additional research skills ------------------------------------
EARNINGS_REVIEW = ResearchSkill(
    key="earnings_review",
    label="Earnings Review",
    target_kind="ticker",
    persona="You are an equity analyst writing a post-earnings thesis update for a holder of the name.",
    outline="""# <Company> (<TICKER>) — Earnings Review
## 1. Headline numbers vs consensus & prior year
## 2. Positive surprises
## 3. Negative surprises
## 4. Guidance changes
## 5. Management tone / call takeaways
## 6. Impact on thesis & valuation
## 7. Action implication (HOLD / ADD / TRIM / RESEARCH MORE)""",
    sidecar_example={
        "ticker": "TICKER", "company": "...", "quarter": "Q_ FY____",
        "analysis_date": "____-__-__", "currency": "EUR",
        "recommendation": "Hold",
        "eps_actual": 0.0, "eps_consensus": 0.0, "revenue_actual": "...", "revenue_consensus": "...",
        "surprise_direction": "beat|miss|inline",
        "thesis_oneliner": "...",
        "guidance_change": "raised|cut|maintained",
        "monitorables": ["..."],
        "thesis_break_triggers": ["..."],
        "catalysts": [{"label": "next earnings", "date": "____-__-__"}],
    },
)

SECTOR_DEEPDIVE = ResearchSkill(
    key="sector_deepdive",
    label="Sector Deep-Dive",
    target_kind="sector",
    persona="You are a thematic/sector strategist writing a deep-dive on a sector or theme.",
    outline="""# <Sector/Theme> — Deep-Dive
## 1. Thesis & why now
## 2. Market size, growth, structure
## 3. Value chain & where profit pools sit
## 4. Key players (incumbents, challengers)
## 5. Demand & supply drivers
## 6. Risks & headwinds
## 7. Best-positioned names (with one-line why)
## 8. How to express the view (and what would invalidate it)""",
    sidecar_example={
        "sector": "...", "analysis_date": "____-__-__",
        "stance": "overweight|neutral|underweight",
        "thesis_oneliner": "...",
        "tam_note": "...", "growth_note": "...",
        "top_picks": [{"ticker": "...", "why": "..."}],
        "key_risks": ["..."],
        "monitorables": ["..."],
        "thesis_break_triggers": ["..."],
        "catalysts": [{"label": "...", "date": "____-__-__"}],
    },
)

PEER_COMPARISON = ResearchSkill(
    key="peer_comparison",
    label="Peer Comparison",
    target_kind="ticker",
    persona="You are an analyst building a rigorous comparables analysis of a name against its peer set.",
    outline="""# <Company> (<TICKER>) vs Peers
## 1. Peer set & why these comps
## 2. Comps table — Mkt cap | P/E | P/S | EV/EBITDA | rev growth | gross/op margin | FCF yield
## 3. Where the name screens cheap / expensive
## 4. Whether the gap is justified (quality, growth, risk)
## 5. Relative-value verdict""",
    sidecar_example={
        "ticker": "TICKER", "company": "...", "analysis_date": "____-__-__", "currency": "EUR",
        "peers": ["PEER1", "PEER2"],
        "recommendation": "Cheap vs peers|In line|Expensive vs peers",
        "thesis_oneliner": "...",
        "relative_multiple_note": "...",
        "comps": [{"ticker": "...", "pe": None, "ev_ebitda": None, "rev_growth_pct": None}],
        "monitorables": ["..."],
        "catalysts": [{"label": "...", "date": "____-__-__"}],
    },
)

VALUATION_REFRESH = ResearchSkill(
    key="valuation_refresh",
    label="Valuation Refresh",
    target_kind="ticker",
    persona="You are a valuation specialist re-running the DCF and reverse-DCF for a name (valuation only — no full deep-dive).",
    outline="""# <Company> (<TICKER>) — Valuation Refresh
## 1. Updated assumptions (growth, margins, WACC, terminal)
## 2. DCF — fair value
## 3. Reverse-DCF — what today's price implies
## 4. Sensitivity (growth × WACC)
## 5. Scenarios — bull / base / bear (probability + implied value)
## 6. Fair-value range & recommendation""",
    sidecar_example={
        "ticker": "TICKER", "company": "...", "analysis_date": "____-__-__", "currency": "EUR",
        "current_price_at_analysis": None,
        "recommendation": "Accumulate|Hold|Trim",
        "fair_value_low": 0, "fair_value_high": 0,
        "upside_low_pct": 0, "upside_high_pct": 0,
        "wacc_pct": 0.0, "terminal_growth_pct": 0.0,
        "thesis_oneliner": "...",
        "scenarios": _SCENARIOS,
        "monitorables": ["..."],
    },
)

MACRO_BRIEF = ResearchSkill(
    key="macro_brief",
    label="Macro Brief",
    target_kind="none",
    persona="You are a macro strategist writing a concise weekly market read for a private investor.",
    outline="""# Macro / Market Brief — <date>
## 1. What moved & why (equities, rates, FX, commodities, crypto)
## 2. Rates & central-bank read
## 3. Growth & inflation pulse
## 4. Key risks on the radar
## 5. Positioning implications
## 6. The week ahead (data + events)""",
    sidecar_example={
        "analysis_date": "____-__-__",
        "regime": "risk-on|risk-off|mixed",
        "thesis_oneliner": "...",
        "key_moves": ["..."],
        "rates_view": "...", "growth_inflation_view": "...",
        "key_risks": ["..."],
        "positioning": ["..."],
        "week_ahead": [{"label": "...", "date": "____-__-__"}],
    },
)

SHORT_THESIS = ResearchSkill(
    key="short_thesis",
    label="Short Thesis",
    target_kind="ticker",
    persona="You are a short-seller building a dedicated, evidence-led bear case on a name. Be rigorous, not sensational.",
    outline="""# <Company> (<TICKER>) — Short Thesis
## 1. One-line short thesis
## 2. What the market is missing
## 3. The bear case (3-5 pillars, each evidenced)
## 4. Quality-of-earnings / balance-sheet red flags
## 5. Downside scenario & price target
## 6. What would break the short (kill criteria)
## 7. Catalysts & timing""",
    sidecar_example={
        "ticker": "TICKER", "company": "...", "analysis_date": "____-__-__", "currency": "EUR",
        "current_price_at_analysis": None,
        "recommendation": "Short|Avoid|No edge",
        "thesis_oneliner": "...",
        "downside_target": 0, "downside_pct": 0,
        "bear_pillars": ["..."],
        "red_flags": ["..."],
        "kill_criteria": ["..."],
        "catalysts": [{"label": "...", "date": "____-__-__"}],
    },
)

INSIDER_SCAN = ResearchSkill(
    key="insider_scan",
    label="Insider / Ownership Scan",
    target_kind="ticker",
    persona="You are an analyst scanning recent insider transactions and ownership changes for a name (Form 4 / 13D-G level).",
    outline="""# <Company> (<TICKER>) — Insider & Ownership Scan
## 1. Recent insider buys / sells (who, size, price)
## 2. Net insider activity read
## 3. Institutional ownership changes (new/exited/added)
## 4. Notable holders & concentration
## 5. Signal vs noise — what it implies for the thesis""",
    sidecar_example={
        "ticker": "TICKER", "company": "...", "analysis_date": "____-__-__",
        "insider_net_signal": "bullish|bearish|neutral",
        "thesis_oneliner": "...",
        "notable_transactions": [{"insider": "...", "side": "buy|sell", "shares": None, "date": "____-__-__"}],
        "institutional_changes": ["..."],
        "monitorables": ["..."],
    },
)

THIRTEEN_F_TRACKER = ResearchSkill(
    key="thirteen_f_tracker",
    label="13F Tracker",
    target_kind="ticker_or_fund",
    persona="You are an analyst reading 13F filings to track institutional positioning in a name or a fund's book.",
    outline="""# <Target> — 13F Tracker
## 1. What this tracks (a name's holders, or a fund's book)
## 2. Latest-quarter position changes (added / trimmed / new / exited)
## 3. Biggest movers by size
## 4. Concentration & conviction read
## 5. Caveats (45-day lag, longs-only, no shorts/derivatives)""",
    sidecar_example={
        "target": "...", "kind": "name|fund", "analysis_date": "____-__-__",
        "quarter": "Q_ ____",
        "net_institutional_signal": "accumulating|distributing|flat",
        "thesis_oneliner": "...",
        "top_changes": [{"holder": "...", "action": "new|added|trimmed|exited", "shares": None}],
        "caveats": ["45-day reporting lag", "longs-only"],
    },
)


# Every skill keyed by its SKILL_REGISTRY name.
SKILLS: dict[str, ResearchSkill] = {
    s.key: s
    for s in (
        STOCK_ANALYSIS, EARNINGS_REVIEW, SECTOR_DEEPDIVE, PEER_COMPARISON,
        VALUATION_REFRESH, MACRO_BRIEF, SHORT_THESIS, INSIDER_SCAN, THIRTEEN_F_TRACKER,
    )
}


# --- public callables (the SKILL_REGISTRY entry points) ----------------------
# Each returns the engine result dict; the background bootstrap str()s it.
def stock_analysis(ticker: str, name: str = "") -> dict:
    extra = f"\nCompany name hint: {name}" if name else ""
    return generate(STOCK_ANALYSIS, target=ticker, extra_context=extra)


def earnings_review(ticker: str) -> dict:
    return generate(EARNINGS_REVIEW, target=ticker)


def sector_deepdive(sector: str) -> dict:
    return generate(SECTOR_DEEPDIVE, target=sector)


def peer_comparison(ticker: str, peers: str = "") -> dict:
    extra = f"\nPeer set to use: {peers}" if peers else ""
    return generate(PEER_COMPARISON, target=ticker, extra_context=extra)


def valuation_refresh(ticker: str) -> dict:
    return generate(VALUATION_REFRESH, target=ticker)


def macro_brief() -> dict:
    return generate(MACRO_BRIEF, target=None)


def short_thesis(ticker: str) -> dict:
    return generate(SHORT_THESIS, target=ticker)


def insider_scan(ticker: str) -> dict:
    return generate(INSIDER_SCAN, target=ticker)


def thirteen_f_tracker(target: str) -> dict:
    return generate(THIRTEEN_F_TRACKER, target=target)
