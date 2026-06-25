"""Unified Skills & Agents registry — the System page's admin list (N2).

ONE canonical catalogue of every skill + agent the dashboard exposes, each with
a domain, a one-line description, and how it is launched (directly from the
registry, or from the page that owns its inputs). The Home page keeps a curated
*quick-run* directory; this is the full admin list with run + delete.

**Delete semantics = soft-disable + archive** (per the Page-7 open decision):
a "deleted" entry is hidden from quick-run, greyed in the admin list, and
refused by the launcher — but never lost. Disabled state is persisted to a
repo-local JSON store with a timestamp + reason, and re-enabling restores it.
Nothing is hard-deleted, so a mis-click is always reversible.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from core.config import DATA_DIR, get_logger
from modules.agents.background import BG_LOG_DIR

logger = get_logger(__name__)

# Repo-local (NOT vault) — pure dashboard state, edited via normal file I/O.
_STATE_FILE = Path(DATA_DIR) / "registry_state.json"


# --- The catalogue -----------------------------------------------------------
# Each entry:
#   key          unique id (also the SKILL_REGISTRY name when run_skill is set)
#   label        display name
#   kind         "agent" (autonomous, multi-step) | "skill" (single callable)
#   domain       wealth | plan | ventures | career | brand | research | system
#   description  one line: what it does
#   run_skill    SKILL_REGISTRY name to POST /api/skills/{name}/run, else None
#   prompt_arg   single free-text arg to collect inline before running, else None
#   run_target   route to the owning page when not directly launchable, else None
#   patterns     lowercase substrings matched against run_ids for last-run health
#   cadence_days how often it should run; older than this ⇒ "due" (None = n/a)
#   note         caveat shown in the row (e.g. "needs inputs — run from …")
REGISTRY: list[dict] = [
    # --- Agents --------------------------------------------------------------
    {
        "key": "market_researcher", "label": "Market Researcher", "kind": "agent",
        "domain": "research",
        "description": "Weekly sector/issuer scan — synthesizes developments, flags thesis-relevant changes.",
        "run_skill": "market_researcher", "prompt_arg": None, "run_target": None,
        "patterns": ("market_research",), "cadence_days": 7, "note": None,
    },
    {
        "key": "earnings_reviewer", "label": "Earnings Reviewer", "kind": "agent",
        "domain": "wealth",
        "description": "Reads a transcript/filing, updates the model, flags what changed vs the thesis.",
        "run_skill": "earnings_reviewer", "prompt_arg": "ticker", "run_target": None,
        "patterns": ("earnings_reviewer", "earnings"), "cadence_days": None, "note": None,
    },
    {
        "key": "valuation_reviewer", "label": "Valuation Reviewer", "kind": "agent",
        "domain": "wealth",
        "description": "Reviews a valuation against comparables and internal methodology standards.",
        "run_skill": None, "prompt_arg": None, "run_target": "/workspace/portfolio",
        "patterns": ("valuation_reviewer", "valuation"), "cadence_days": None,
        "note": "needs inputs — run from the Portfolio workspace",
    },
    {
        "key": "model_builder", "label": "Model Builder", "kind": "agent",
        "domain": "wealth",
        "description": "Builds/maintains a financial model from filings, data feeds and assumptions.",
        "run_skill": None, "prompt_arg": None, "run_target": "/workspace/portfolio",
        "patterns": ("model_builder",), "cadence_days": None,
        "note": "needs inputs — run from the Portfolio workspace",
    },
    {
        "key": "idea_validator", "label": "Idea Validator", "kind": "agent",
        "domain": "ventures",
        "description": "12-stage idea validation workflow (brief → market → decision), per idea.",
        "run_skill": None, "prompt_arg": None, "run_target": "/ideas",
        "patterns": ("stage_", "validate_"), "cadence_days": None,
        "note": "run per-idea from the Ideas page",
    },
    {
        "key": "ask_about_project", "label": "Ask About Project", "kind": "agent",
        "domain": "ventures",
        "description": "Q&A grounded in a single project's folder (CLAUDE.md + README + key files).",
        "run_skill": None, "prompt_arg": None, "run_target": "/projects",
        "patterns": ("ask_about_project",), "cadence_days": None,
        "note": "pick a project — run from the Projects page",
    },
    {
        "key": "ask_anything", "label": "Ask Anything", "kind": "agent",
        "domain": "system",
        "description": "Open-ended question answered over the whole vault.",
        "run_skill": "ask_anything", "prompt_arg": "question", "run_target": None,
        "patterns": ("ask_anything",), "cadence_days": None, "note": None,
    },
    {
        "key": "daily_priorities", "label": "Daily Priorities", "kind": "agent",
        "domain": "plan",
        "description": "Suggests 3–5 priorities for the day from open tasks + hard deadlines.",
        "run_skill": None, "prompt_arg": None, "run_target": "/",
        "patterns": ("daily_priorit", "priorities"), "cadence_days": 1,
        "note": "generate from the Home / Plan priorities panel",
    },
    {
        "key": "planner_ai", "label": "Planner AI", "kind": "agent",
        "domain": "plan",
        "description": "Recommends where to place pool tasks across the week grid.",
        "run_skill": None, "prompt_arg": None, "run_target": "/planner",
        "patterns": ("planner", "placement", "ai_recommend"), "cadence_days": None,
        "note": "run from the planner's AI assistant",
    },
    {
        "key": "weekly_briefing", "label": "Weekly Briefing", "kind": "agent",
        "domain": "system",
        "description": "Sunday-evening briefing across projects, finance and the week ahead.",
        "run_skill": None, "prompt_arg": None, "run_target": None,
        "patterns": ("weekly_brief", "briefing"), "cadence_days": 7,
        "note": "auto-scheduled Sunday 18:00",
    },
    # --- Research skills (Phase C) -------------------------------------------
    # Each emits a .docx + .json sidecar into the Reports library and runs in the
    # background via the generic skill launcher (same runner as Idea Validation).
    {
        "key": "stock_analysis", "label": "Stock Analysis", "kind": "skill",
        "domain": "research",
        "description": "Full 12-section equity deep-dive (DCF + reverse-DCF + scenarios) → .docx + JSON sidecar.",
        "run_skill": "stock_analysis", "prompt_arg": "ticker", "run_target": None,
        "patterns": ("stock_analysis",), "cadence_days": None, "note": None,
    },
    {
        "key": "earnings_review", "label": "Earnings Review", "kind": "skill",
        "domain": "research",
        "description": "Post-earnings thesis update for a ticker → .docx + JSON sidecar.",
        "run_skill": "earnings_review", "prompt_arg": "ticker", "run_target": None,
        "patterns": ("earnings_review",), "cadence_days": None, "note": None,
    },
    {
        "key": "sector_deepdive", "label": "Sector Deep-Dive", "kind": "skill",
        "domain": "research",
        "description": "Thematic/sector deep-dive (TAM, value chain, best-positioned names) → .docx + JSON sidecar.",
        "run_skill": "sector_deepdive", "prompt_arg": "sector", "run_target": None,
        "patterns": ("sector_deepdive",), "cadence_days": None, "note": None,
    },
    {
        "key": "peer_comparison", "label": "Peer Comparison", "kind": "skill",
        "domain": "research",
        "description": "Comparables analysis of a ticker vs its peer set → .docx + JSON sidecar.",
        "run_skill": "peer_comparison", "prompt_arg": "ticker", "run_target": None,
        "patterns": ("peer_comparison",), "cadence_days": None, "note": None,
    },
    {
        "key": "valuation_refresh", "label": "Valuation Refresh", "kind": "skill",
        "domain": "research",
        "description": "Re-run DCF + reverse-DCF + scenarios only for a ticker → .docx + JSON sidecar.",
        "run_skill": "valuation_refresh", "prompt_arg": "ticker", "run_target": None,
        "patterns": ("valuation_refresh",), "cadence_days": None, "note": None,
    },
    {
        "key": "macro_brief", "label": "Macro Brief", "kind": "skill",
        "domain": "research",
        "description": "Weekly macro / market read (rates, growth, risks, week ahead) → .docx + JSON sidecar.",
        "run_skill": "macro_brief", "prompt_arg": None, "run_target": None,
        "patterns": ("macro_brief",), "cadence_days": 7, "note": None,
    },
    {
        "key": "short_thesis", "label": "Short Thesis", "kind": "skill",
        "domain": "research",
        "description": "Dedicated bear/short case + downside scenario for a ticker → .docx + JSON sidecar.",
        "run_skill": "short_thesis", "prompt_arg": "ticker", "run_target": None,
        "patterns": ("short_thesis",), "cadence_days": None, "note": None,
    },
    {
        "key": "insider_scan", "label": "Insider / Ownership Scan", "kind": "skill",
        "domain": "research",
        "description": "Recent insider transactions + ownership changes for a ticker → .docx + JSON sidecar.",
        "run_skill": "insider_scan", "prompt_arg": "ticker", "run_target": None,
        "patterns": ("insider_scan",), "cadence_days": None, "note": None,
    },
    {
        "key": "thirteen_f_tracker", "label": "13F Tracker", "kind": "skill",
        "domain": "research",
        "description": "Institutional 13F holdings + position changes for a name or fund → .docx + JSON sidecar.",
        "run_skill": "thirteen_f_tracker", "prompt_arg": "target", "run_target": None,
        "patterns": ("thirteen_f_tracker", "13f"), "cadence_days": None, "note": None,
    },
    # --- Wealth skills -------------------------------------------------------
    {
        "key": "generate_thesis_statement", "label": "Generate Thesis Statement", "kind": "skill",
        "domain": "wealth",
        "description": "Drafts an investment thesis statement for a watchlist ticker.",
        "run_skill": "generate_thesis_statement", "prompt_arg": "ticker", "run_target": None,
        "patterns": ("generate_thesis_statement", "thesis"), "cadence_days": None, "note": None,
    },
    {
        "key": "summarize_filing", "label": "Summarize Filing", "kind": "skill",
        "domain": "wealth",
        "description": "Summarizes a filing for a ticker into thesis-relevant points.",
        "run_skill": None, "prompt_arg": None, "run_target": "/watchlist",
        "patterns": ("summarize_filing",), "cadence_days": None,
        "note": "needs a filing URL — run from Watchlist",
    },
    {
        "key": "compare_to_peers", "label": "Compare to Peers", "kind": "skill",
        "domain": "wealth",
        "description": "Compares a ticker to a named peer set.",
        "run_skill": None, "prompt_arg": None, "run_target": "/watchlist",
        "patterns": ("compare_to_peers",), "cadence_days": None,
        "note": "needs a peer list — run from Watchlist",
    },
    {
        "key": "portfolio_scenario", "label": "Portfolio Scenario", "kind": "skill",
        "domain": "wealth",
        "description": "Runs a what-if scenario across the portfolio from a plain-text description.",
        "run_skill": "portfolio_scenario", "prompt_arg": "scenario_description", "run_target": None,
        "patterns": ("portfolio_scenario", "scenario"), "cadence_days": None, "note": None,
    },
    {
        "key": "why_is_x_moving", "label": "Why Is X Moving", "kind": "skill",
        "domain": "wealth",
        "description": "Explains why a holding is moving today.",
        "run_skill": "why_is_x_moving", "prompt_arg": "ticker", "run_target": None,
        "patterns": ("why_is_x_moving",), "cadence_days": None, "note": None,
    },
    {
        "key": "rebalance_suggestor", "label": "Rebalance Suggestor", "kind": "skill",
        "domain": "wealth",
        "description": "Suggests trades to reach a target allocation.",
        "run_skill": None, "prompt_arg": None, "run_target": "/portfolio",
        "patterns": ("rebalance_suggestor", "rebalance"), "cadence_days": None,
        "note": "needs a target allocation — run from Portfolio",
    },
    {
        "key": "add_hypothesis", "label": "Add Hypothesis", "kind": "skill",
        "domain": "wealth",
        "description": "Records a new investment hypothesis for a ticker.",
        "run_skill": None, "prompt_arg": None, "run_target": "/watchlist",
        "patterns": ("add_hypothesis",), "cadence_days": None,
        "note": "run from Watchlist",
    },
    {
        "key": "quarterly_portfolio_review", "label": "Quarterly Portfolio Review", "kind": "skill",
        "domain": "wealth",
        "description": "Full quarterly review of the portfolio.",
        "run_skill": "quarterly_portfolio_review", "prompt_arg": None, "run_target": None,
        "patterns": ("quarterly_portfolio",), "cadence_days": 90, "note": None,
    },
    {
        "key": "tax_scenario", "label": "Tax Scenario", "kind": "skill",
        "domain": "wealth",
        "description": "Estimates the tax impact of a described scenario (Abgeltungsteuer etc.).",
        "run_skill": "tax_scenario", "prompt_arg": "scenario_description", "run_target": None,
        "patterns": ("tax_scenario",), "cadence_days": None, "note": None,
    },
    {
        "key": "forecast_cash_flow", "label": "Forecast Cash Flow", "kind": "skill",
        "domain": "wealth",
        "description": "Projects cash flow, optionally under a described scenario.",
        "run_skill": "forecast_cash_flow", "prompt_arg": "scenario_description", "run_target": None,
        "patterns": ("forecast_cash_flow", "cash_flow"), "cadence_days": None, "note": None,
    },
    {
        "key": "find_expense_optimizations", "label": "Find Expense Optimizations", "kind": "skill",
        "domain": "wealth",
        "description": "Scans spend categories for savings opportunities.",
        "run_skill": "find_expense_optimizations", "prompt_arg": None, "run_target": None,
        "patterns": ("find_expense_optimizations", "expense"), "cadence_days": None, "note": None,
    },
    {
        "key": "quarterly_money_review", "label": "Quarterly Money Review", "kind": "skill",
        "domain": "wealth",
        "description": "Full quarterly review of personal finances.",
        "run_skill": "quarterly_money_review", "prompt_arg": None, "run_target": None,
        "patterns": ("quarterly_money",), "cadence_days": 90, "note": None,
    },
    {
        "key": "tax_deductible_review", "label": "Tax Deductible Review", "kind": "skill",
        "domain": "wealth",
        "description": "Reviews spend for tax-deductible items.",
        "run_skill": "tax_deductible_review", "prompt_arg": None, "run_target": None,
        "patterns": ("tax_deductible",), "cadence_days": None, "note": None,
    },
    {
        "key": "bill_forecaster", "label": "Bill Forecaster", "kind": "skill",
        "domain": "wealth",
        "description": "Forecasts upcoming bills and recurring charges.",
        "run_skill": "bill_forecaster", "prompt_arg": None, "run_target": None,
        "patterns": ("bill_forecaster", "bill"), "cadence_days": None, "note": None,
    },
    # --- Career skills (launched from the Career page) -----------------------
    {
        "key": "quiz_technicals", "label": "Quiz: Technicals", "kind": "skill",
        "domain": "career",
        "description": "Generates a technical quiz for a chosen module.",
        "run_skill": None, "prompt_arg": None, "run_target": "/career",
        "patterns": ("quiz_technicals",), "cadence_days": None,
        "note": "run from Career",
    },
    {
        "key": "mock_interview", "label": "Mock Interview", "kind": "skill",
        "domain": "career",
        "description": "Runs a mock interview (technical / behavioural).",
        "run_skill": None, "prompt_arg": None, "run_target": "/career",
        "patterns": ("mock_interview",), "cadence_days": None,
        "note": "run from Career",
    },
    {
        "key": "deal_note", "label": "Deal Note", "kind": "skill",
        "domain": "career",
        "description": "Turns an article into a structured deal note.",
        "run_skill": None, "prompt_arg": None, "run_target": "/career",
        "patterns": ("deal_note",), "cadence_days": None,
        "note": "run from Career",
    },
    {
        "key": "model_checker", "label": "Model Checker", "kind": "skill",
        "domain": "career",
        "description": "Sanity-checks a financial model summary.",
        "run_skill": None, "prompt_arg": None, "run_target": "/career",
        "patterns": ("model_checker",), "cadence_days": None,
        "note": "run from Career",
    },
    {
        "key": "industry_primer", "label": "Industry Primer", "kind": "skill",
        "domain": "career",
        "description": "Produces a primer on a sector.",
        "run_skill": None, "prompt_arg": None, "run_target": "/career",
        "patterns": ("industry_primer",), "cadence_days": None,
        "note": "run from Career",
    },
    {
        "key": "career_letter_draft", "label": "Career Letter Draft", "kind": "skill",
        "domain": "career",
        "description": "Drafts a career-related letter (e.g. correspondence).",
        "run_skill": None, "prompt_arg": None, "run_target": "/career",
        "patterns": ("career_letter_draft", "letter"), "cadence_days": None,
        "note": "run from Career",
    },
    # --- Brand skills (launched per-video from the Brand page) ---------------
    {
        "key": "generate_hook_variants", "label": "Generate Hook Variants", "kind": "skill",
        "domain": "brand",
        "description": "Drafts hook variants for a video.",
        "run_skill": None, "prompt_arg": None, "run_target": "/brand",
        "patterns": ("generate_hook_variants", "hook"), "cadence_days": None,
        "note": "run per-video from Brand",
    },
    {
        "key": "draft_first_pass_script", "label": "Draft First-Pass Script", "kind": "skill",
        "domain": "brand",
        "description": "Drafts a first-pass script for a video.",
        "run_skill": None, "prompt_arg": None, "run_target": "/brand",
        "patterns": ("draft_first_pass_script", "script"), "cadence_days": None,
        "note": "run per-video from Brand",
    },
    {
        "key": "generate_shot_list", "label": "Generate Shot List", "kind": "skill",
        "domain": "brand",
        "description": "Generates a shot list for a video.",
        "run_skill": None, "prompt_arg": None, "run_target": "/brand",
        "patterns": ("generate_shot_list", "shot"), "cadence_days": None,
        "note": "run per-video from Brand",
    },
    {
        "key": "generate_title_variants", "label": "Generate Title Variants", "kind": "skill",
        "domain": "brand",
        "description": "Drafts title variants for a video.",
        "run_skill": None, "prompt_arg": None, "run_target": "/brand",
        "patterns": ("generate_title_variants", "title"), "cadence_days": None,
        "note": "run per-video from Brand",
    },
    {
        "key": "generate_description_tags", "label": "Generate Description + Tags", "kind": "skill",
        "domain": "brand",
        "description": "Writes the description and tags for a video.",
        "run_skill": None, "prompt_arg": None, "run_target": "/brand",
        "patterns": ("generate_description_tags", "description"), "cadence_days": None,
        "note": "run per-video from Brand",
    },
    {
        "key": "generate_thumbnail_copy", "label": "Generate Thumbnail Copy", "kind": "skill",
        "domain": "brand",
        "description": "Drafts thumbnail copy for a video.",
        "run_skill": None, "prompt_arg": None, "run_target": "/brand",
        "patterns": ("generate_thumbnail_copy", "thumbnail"), "cadence_days": None,
        "note": "run per-video from Brand",
    },
    {
        "key": "ask_claude_about_video", "label": "Ask About Video", "kind": "skill",
        "domain": "brand",
        "description": "Q&A grounded in a single video's 10-section folder.",
        "run_skill": None, "prompt_arg": None, "run_target": "/brand",
        "patterns": ("ask_claude_about_video",), "cadence_days": None,
        "note": "run per-video from Brand",
    },
]

_BY_KEY = {e["key"]: e for e in REGISTRY}


# --- Soft-disable / archive persistence --------------------------------------
def _load_state() -> dict:
    if not _STATE_FILE.exists():
        return {"disabled": {}}
    try:
        data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        data.setdefault("disabled", {})
        return data
    except (json.JSONDecodeError, OSError):
        logger.warning("registry_state.json unreadable — treating as empty", exc_info=True)
        return {"disabled": {}}


def _save_state(state: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def disabled_keys() -> dict[str, dict]:
    """Map of key -> archive record ({disabled_at, reason}) for disabled entries."""
    return _load_state().get("disabled", {})


def is_disabled(key: str) -> bool:
    return key in disabled_keys()


def disable(key: str, reason: str | None = None) -> dict:
    """Soft-disable (archive) an entry. Idempotent; nothing is lost."""
    if key not in _BY_KEY:
        raise KeyError(key)
    state = _load_state()
    state["disabled"][key] = {
        "disabled_at": datetime.now().isoformat(timespec="seconds"),
        "reason": reason,
    }
    _save_state(state)
    logger.info("registry entry soft-disabled: %s (reason=%s)", key, reason)
    return state["disabled"][key]


def enable(key: str) -> None:
    """Restore a previously disabled entry."""
    state = _load_state()
    if state["disabled"].pop(key, None) is not None:
        _save_state(state)
        logger.info("registry entry re-enabled: %s", key)


def disabled_skill_names() -> set[str]:
    """SKILL_REGISTRY names whose registry entry is currently disabled.

    Used by the launcher to refuse running a soft-disabled skill/agent.
    """
    disabled = disabled_keys()
    return {
        e["run_skill"]
        for e in REGISTRY
        if e["run_skill"] and e["key"] in disabled
    }


# --- Last-run health ---------------------------------------------------------
def _latest_runs_by_pattern() -> dict[str, dict]:
    """Newest background run per registry entry, matched by run_id substring."""
    latest: dict[str, dict] = {}
    if not BG_LOG_DIR.exists():
        return latest
    for f in sorted(BG_LOG_DIR.glob("*.status.json"), key=lambda p: p.name):
        run_id = f.name.removesuffix(".status.json")
        run_lower = run_id.lower()
        for entry in REGISTRY:
            if any(pat in run_lower for pat in entry["patterns"]):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                data["run_id"] = run_id
                # Filenames sort chronologically (timestamp prefix); last wins = newest.
                latest[entry["key"]] = data
    return latest


def _run_timestamp(run: dict) -> datetime | None:
    for field in ("completed_at", "failed_at", "cancelled_at", "started_at"):
        raw = run.get(field)
        if raw:
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                continue
    try:
        return datetime.strptime(run["run_id"][:15], "%Y%m%d_%H%M%S")
    except (KeyError, ValueError):
        return None


def list_entries() -> list[dict]:
    """The full registry with per-entry health + disabled state.

    Health legend: ``ok`` ran recently / ``due`` cadence exceeded / ``failed``
    last run errored / ``never`` no run on record. Disabled entries report their
    health too, so re-enabling shows the real last state.
    """
    runs = _latest_runs_by_pattern()
    disabled = disabled_keys()
    now = datetime.now()
    out = []
    for entry in REGISTRY:
        run = runs.get(entry["key"])
        ts = _run_timestamp(run) if run else None
        if run is None:
            status = "never"
        elif run.get("status") in {"failed", "cancelled"}:
            status = "failed"
        elif run.get("status") == "running":
            status = "ok"
        elif entry["cadence_days"] and ts and (now - ts).days > entry["cadence_days"]:
            status = "due"
        else:
            status = "ok"
        archive = disabled.get(entry["key"])
        out.append({
            "key": entry["key"],
            "label": entry["label"],
            "kind": entry["kind"],
            "domain": entry["domain"],
            "description": entry["description"],
            "health": status,
            "last_run_at": ts.isoformat() if ts else None,
            "last_run_id": run.get("run_id") if run else None,
            "last_run_status": run.get("status") if run else None,
            "run_skill": entry["run_skill"],
            "prompt_arg": entry["prompt_arg"],
            "run_target": entry["run_target"],
            "cadence_days": entry["cadence_days"],
            "note": entry["note"],
            "disabled": archive is not None,
            "disabled_at": archive.get("disabled_at") if archive else None,
            "disabled_reason": archive.get("reason") if archive else None,
        })
    return out
