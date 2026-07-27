"""Pydantic models for the Personal Command Center API.

Response models that map cleanly to a fixed shape (tasks, runs, search) are used
directly. Endpoints that wrap pandas frames or free-form vault structures return
plain JSON-safe dicts/lists instead, to stay robust against source-sheet drift —
those still appear in the OpenAPI schema as generic objects.
"""
from __future__ import annotations

from datetime import datetime, date
from typing import Optional, Literal, Any

from pydantic import BaseModel


# --- Tasks ------------------------------------------------------------------
class Task(BaseModel):
    text: str
    checked: bool
    section: str  # "This week" / "Next week" / "Bigger items" / etc.
    line_index: int
    is_task: bool = True  # False for plain dated preview bullets (e.g. Next week)


class HardDate(BaseModel):
    date: date
    label: str
    raw: str


class TaskToggleRequest(BaseModel):
    section: str
    line_index: int


class TaskAddRequest(BaseModel):
    section: str
    text: str


class ToggleByTextRequest(BaseModel):
    match: str  # fuzzy search string for the task to toggle (used by Jarvis voice)


# --- Projects ---------------------------------------------------------------
class ProjectCard(BaseModel):
    id: str  # "01", "02", ...
    name: str
    status: Literal["on_track", "needs_attention", "at_risk", "done", "unknown"]
    status_emoji: str  # legacy from MD; UI may ignore
    status_text: str = ""
    big_milestone: Optional[str] = None
    big_milestone_date: Optional[date] = None
    next_step: Optional[str] = None
    folder: str = ""
    flow: Optional[str] = None  # "A" | "B" parsed from README "**Type:** Flow X"
    has_agents: bool = False  # venture has an _agents.json roster
    # --- Projects pillar enrichment (Phase E, spec § e) ---------------------
    phase: Optional[str] = None  # short phase label (from the index Status line)
    open_task_count: int = 0  # open project-tagged tasks in the captures DB
    top_task: Optional[str] = None  # newest open task for this project
    last_activity: Optional[datetime] = None  # mtime of the latest content file


class BriefingCard(BaseModel):
    """Latest weekly briefing summary for the small Projects-pillar card."""
    date: Optional[str] = None  # YYYY-MM-DD parsed from the filename
    title: str
    path: str = ""
    excerpt: str = ""
    count: int = 0  # total briefings on file


class ProjectLogEntry(BaseModel):
    note: str


class ProjectNextStepToggleRequest(BaseModel):
    line_index: int


class ProjectCreateRequest(BaseModel):
    name: str
    flow: str = "A"
    seed: str = ""


# --- Ideas ------------------------------------------------------------------
class IdeaCard(BaseModel):
    name: str
    stages_complete: int
    progress: int  # 0-12
    state: dict = {}
    next_stage: Optional[str] = None  # first missing/stale stage key, or None if complete


class IdeaCreateRequest(BaseModel):
    name: str
    brief_text: str


class StageRunRequest(BaseModel):
    stage_key: str


class IdeaDecisionRequest(BaseModel):
    decision: Literal["Pursue", "Park", "Kill"]
    reason: str = ""


class IdeaOverridesRequest(BaseModel):
    text: str


# --- Inbox ------------------------------------------------------------------
class InboxCaptureRequest(BaseModel):
    content: str
    source: str = "quickcapture"


class InboxActionRequest(BaseModel):
    action: Literal["archive", "delete", "move", "convert_to_task"]
    project_id: Optional[str] = None  # for "move"
    section: Optional[str] = None     # for "convert_to_task"
    title: Optional[str] = None       # for "convert_to_task"


# --- Portfolio --------------------------------------------------------------
class Holding(BaseModel):
    ticker: str
    name: str
    type: str
    quantity: Optional[float] = None
    avg_cost: Optional[float] = None
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    pnl_since_bought_pct: Optional[float] = None
    pnl_ytd_pct: Optional[float] = None
    pnl_last_week_pct: Optional[float] = None
    currency: str = "EUR"


class PortfolioSnapshot(BaseModel):
    total_value: float
    position_count: int
    last_snapshot_date: Optional[str] = None
    holdings: list[dict]


# --- Money ------------------------------------------------------------------
class MoneySnapshot(BaseModel):
    cash_balance: Optional[float] = None
    net_worth: Optional[float] = None
    net_worth_breakdown: dict = {}
    monthly_burn: Optional[float] = None
    runway_months: Optional[float] = None


class TaxScenarioRequest(BaseModel):
    scenario_description: str
    save_to_project: Optional[str] = None


class ContributionOverrideRequest(BaseModel):
    # None clears the override for that month, reverting to the estimate/explicit source.
    value: Optional[float] = None


# --- Cash Flow pillar ---------------------------------------------------------
class ReserveBalanceRequest(BaseModel):
    value: float


class CashflowGoalRequest(BaseModel):
    # None clears the goal.
    value: Optional[float] = None


class CashflowBudgetRequest(BaseModel):
    category: str
    # None clears that category's target.
    value: Optional[float] = None


class CashflowResolveRequest(BaseModel):
    """Answer payload for one flagged ledger entry (all fields optional — only
    send what David's answer actually changes; ``needs_review`` always clears)."""

    date: Optional[date] = None
    direction: Optional[Literal["income", "expense"]] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    account: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None


# --- Watchlist --------------------------------------------------------------
class WatchlistAddRequest(BaseModel):
    ticker: str
    name: str = ""
    notes: str = ""
    # Target section to append under in Watchlist.md: a tier key ("tier1"/"tier2"),
    # a Tier-3 letter ("A".."N"), or "adhoc" (the default Ad-hoc section).
    section: str = "adhoc"
    # Deprecated (JSON-era) fields — accepted but ignored now that Watchlist.md
    # is the source of truth. Kept so older clients don't 422.
    status: str = "researching"
    tier: str = "Tier 3"


class WatchlistHypothesisRequest(BaseModel):
    # The watchlist UI sends ``hypothesis``; the Jarvis voice hook sends ``text``.
    # Either is accepted — the endpoint resolves whichever is present.
    hypothesis: str = ""
    text: str = ""


# --- Brand ------------------------------------------------------------------
class BrandVideoCreateRequest(BaseModel):
    title: str
    platform: str
    concept: str = ""


class BrandSkillRequest(BaseModel):
    skill: str                     # e.g. "generate_hook_variants"
    question: Optional[str] = None  # only for ask_claude_about_video


class BrandStageMoveRequest(BaseModel):
    # Target pipeline stage (IDEAS/SCRIPTING/FILMING/EDITING/PUBLISHED). When
    # omitted, the video advances to the next stage.
    stage: Optional[str] = None


class BrandEditRequest(BaseModel):
    # "New edit" trigger (Remotion stub). Either field optional.
    video_name: Optional[str] = None
    note: Optional[str] = None


# --- Career -----------------------------------------------------------------
class CareerSkillRequest(BaseModel):
    skill: str                  # quiz_technicals / mock_interview / deal_note / ...
    arg: Optional[str] = None   # module / kind / sector / article_text ...
    context: Optional[str] = None  # for career_letter_draft


class CareerChecklistToggleRequest(BaseModel):
    checklist: Literal["onboarding", "technicals"]
    index: int


# --- Background runs --------------------------------------------------------
class RunStatus(BaseModel):
    run_id: str
    label: Optional[str] = None
    status: str = "unknown"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    failed_at: Optional[str] = None
    log_file: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    detail: Optional[str] = None


class RunLaunchResponse(BaseModel):
    run_id: str
    pid: Optional[int] = None
    label: str
    log_file: Optional[str] = None
    status_file: Optional[str] = None
    launched_at: Optional[str] = None


# --- Skills -----------------------------------------------------------------
class SkillRunRequest(BaseModel):
    args: dict[str, Any] = {}
    label: Optional[str] = None


# --- Search -----------------------------------------------------------------
class SearchResult(BaseModel):
    relative_path: str
    snippet: str
    match_count: int
    mtime: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
