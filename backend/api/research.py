"""Research API (Phase D — Research tab: run launcher + Reports library + hypotheses).

Thin HTTP adapter over the Phase C research engine. The run launcher reuses the
EXISTING background runner (``modules.agents.background.launch`` — same infra as
Idea Validation); reports come from the sidecar index the engine maintains. The
dashboard reads the JSON sidecars, never the .docx.

The Decision Log (model C) is served by the existing ``/api/finance/journal/*``
routes — it is the shared research store, so it is not duplicated here.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config import HYPOTHESIS_TRACKER_FILE, get_logger
from modules.agents import background
from modules.agents.skills.research import engine
from modules.agents.skills.research.skills import SKILLS
from modules.finance.price_history import fx_rate_to_eur, latest_price_eur

logger = get_logger(__name__)

router = APIRouter()

# Monetary sidecar fields to convert native->EUR for display (Phase H).
_FV_KEYS = ("fair_value_low", "fair_value_high")


def _enrich_report_eur(report: dict | None) -> dict | None:
    """Augment a sidecar with EUR-converted valuation fields (Portfolio is EUR-everywhere).

    Reports may be written in a native currency (e.g. NKE in USD). The Plan card +
    Reports library must DISPLAY EUR (v3 spec § d, locked 2026-06-26): convert
    ``fair_value_low/high`` + each scenario's ``implied_value`` at the current
    native->EUR FX rate, attach the live EUR price, and recompute upside vs that
    live EUR price. Originals are kept untouched; converted values get an ``_eur``
    suffix. Best-effort — on any failure the report is returned unchanged so the
    card still renders in native terms rather than breaking the endpoint.
    """
    if not report:
        return report
    try:
        native = (report.get("currency") or "EUR").upper()
        ticker = report.get("ticker") or report.get("target")
        rate, stale = fx_rate_to_eur(native)
        report["native_currency"] = native
        report["display_currency"] = "EUR"
        report["fx_to_eur"] = rate
        report["fx_stale"] = stale

        live = latest_price_eur(str(ticker)) if ticker else None
        live_eur = round(live.eur_price, 2) if live else None
        report["live_price_eur"] = live_eur

        if rate is not None:
            for k in _FV_KEYS:
                v = report.get(k)
                if isinstance(v, (int, float)):
                    report[f"{k}_eur"] = round(v * rate, 2)
            cpa = report.get("current_price_at_analysis")
            if isinstance(cpa, (int, float)):
                report["current_price_at_analysis_eur"] = round(cpa * rate, 2)
            scenarios = report.get("scenarios")
            if isinstance(scenarios, dict):
                for s in scenarios.values():
                    iv = s.get("implied_value") if isinstance(s, dict) else None
                    if isinstance(iv, (int, float)):
                        s["implied_value_eur"] = round(iv * rate, 2)

        # Upside vs the LIVE EUR price (the authoritative denominator).
        if live_eur:
            fvl = report.get("fair_value_low_eur")
            fvh = report.get("fair_value_high_eur")
            if isinstance(fvl, (int, float)):
                report["upside_low_pct_eur"] = round((fvl / live_eur - 1) * 100, 1)
            if isinstance(fvh, (int, float)):
                report["upside_high_pct_eur"] = round((fvh / live_eur - 1) * 100, 1)
    except Exception:  # noqa: BLE001 - display enrichment must never break the endpoint
        logger.warning("EUR enrichment failed for %s", (report or {}).get("ticker"), exc_info=True)
    return report

# The research callables all live in this package; each takes its target as the
# first positional arg (macro_brief takes none). This mirrors the SKILL_REGISTRY
# in backend/api/skills.py — kept here so the launcher can validate targets.
_RESEARCH_MODULE = "modules.agents.skills.research"


class RunResearchRequest(BaseModel):
    skill: str                  # one of SKILLS keys, e.g. "stock_analysis"
    target: str | None = None   # ticker / sector / fund (None for macro_brief)
    extra: str | None = None    # optional 2nd arg (company name hint / peer set)


@router.get("/skills")
def list_skills() -> dict:
    """The runnable research skills for the launcher dropdown (key, label, target_kind)."""
    return {
        "skills": [
            {"key": s.key, "label": s.label, "target_kind": s.target_kind}
            for s in SKILLS.values()
        ]
    }


@router.get("/reports")
def list_reports() -> dict:
    """Every report sidecar on disk, newest first — powers the Reports library."""
    reports = [_enrich_report_eur(r) for r in engine.list_reports()]
    return {"reports": reports, "count": len(reports)}


@router.get("/reports/latest/{ticker}")
def latest_report(ticker: str) -> dict:
    """Latest stock-analysis sidecar for a ticker — the PositionPlanCard source."""
    report = _enrich_report_eur(engine.latest_for_ticker(ticker))
    return {"ticker": ticker.strip().upper(), "report": report}


@router.post("/run")
def run_research(req: RunResearchRequest) -> dict:
    """Enqueue a research skill as a background job (reuses the existing runner)."""
    skill = SKILLS.get(req.skill)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"unknown research skill: {req.skill}")

    target = (req.target or "").strip()
    if skill.target_kind != "none" and not target:
        raise HTTPException(status_code=400, detail=f"{skill.label} needs a target ({skill.target_kind}).")

    args: list = [] if skill.target_kind == "none" else [target]
    if req.extra and skill.key in {"stock_analysis", "peer_comparison"}:
        args.append(req.extra.strip())

    label = f"{skill.label}: {target}" if target else skill.label
    info = background.launch(
        module_path=_RESEARCH_MODULE, callable_name=skill.key, args=args, label=label,
    )
    return {"ok": True, "run_id": info["run_id"], "skill": skill.key, "target": target or None}


@router.get("/hypotheses")
def hypotheses() -> dict:
    """Open hypotheses parsed from the vault Hypothesis_Tracker.md (the shared store).

    Each block starts at a bold ``**H..`` / ``**[TICKER]`` marker (same convention
    the Market Researcher agent writes). Returns raw blocks; the UI renders them.
    """
    if not HYPOTHESIS_TRACKER_FILE.exists():
        return {"hypotheses": [], "count": 0, "source": None}
    text = HYPOTHESIS_TRACKER_FILE.read_text(encoding="utf-8")
    blocks = [b.strip() for b in re.split(r"\n(?=\*\*\[?[A-Z0-9])", text) if b.strip()]
    # Drop a leading title/preamble block that has no bold marker.
    blocks = [b for b in blocks if b.startswith("**")]
    return {
        "hypotheses": [{"text": b} for b in blocks],
        "count": len(blocks),
        "source": "Hypothesis_Tracker.md",
    }
