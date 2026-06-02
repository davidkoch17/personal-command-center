/**
 * API type definitions — hand-mirrored from `backend/models/schemas.py`.
 * Keep in sync with the Pydantic models. Endpoints that wrap pandas frames or
 * free-form vault structures return generic `Record<string, unknown>` shapes.
 */

// --- Tasks ------------------------------------------------------------------
export interface Task {
  text: string
  checked: boolean
  section: string // "This week" / "Next week" / "Bigger items" / etc.
  line_index: number
  is_task?: boolean // false for plain dated preview bullets (e.g. Next week)
}

// --- Hard dates -------------------------------------------------------------
export interface HardDate {
  date: string // ISO YYYY-MM-DD
  label: string
  raw: string
}

// --- Priorities -------------------------------------------------------------
export interface PriorityItem {
  rank: number
  task: string
  deadline?: string | null
  rationale?: string
}

export interface PrioritySuggestion {
  recommendation: string
  ordered: PriorityItem[]
}

export interface TaskToggleRequest {
  section: string
  line_index: number
}

export interface TaskAddRequest {
  section: string
  text: string
}

// --- Projects ---------------------------------------------------------------
export type ProjectStatus =
  | "on_track"
  | "needs_attention"
  | "at_risk"
  | "done"
  | "unknown"

export interface ProjectCard {
  id: string // "01", "02", ...
  name: string
  status: ProjectStatus
  status_emoji: string // legacy from MD; UI may ignore
  status_text: string
  big_milestone?: string | null
  big_milestone_date?: string | null // ISO date
  next_step?: string | null
  folder: string
}

export interface ProjectLogEntry {
  note: string
}

export interface ProjectNextStepToggleRequest {
  line_index: number
}

export interface ProjectCreateRequest {
  name: string
  flow?: string
  seed?: string
}

/** Free-form deep-dive workspace payload (vault-structure dependent). */
export type ProjectWorkspace = Record<string, unknown>

// --- Ideas ------------------------------------------------------------------
export interface IdeaCard {
  name: string
  stages_complete: number
  progress: number // 0-12
  state: Record<string, unknown>
}

export interface IdeaCreateRequest {
  name: string
  brief_text: string
}

export interface StageRunRequest {
  stage_key: string
}

export type IdeaDecision = "Pursue" | "Park" | "Kill"

export interface IdeaDecisionRequest {
  decision: IdeaDecision
  reason?: string
}

export interface IdeaOverridesRequest {
  text: string
}

export type IdeaWorkspace = Record<string, unknown>

// --- Inbox ------------------------------------------------------------------
export interface InboxCaptureRequest {
  content: string
  source?: string
}

export type InboxAction = "archive" | "delete" | "move" | "convert_to_task"

export interface InboxActionRequest {
  action: InboxAction
  project_id?: string | null // for "move"
  section?: string | null // for "convert_to_task"
  title?: string | null // for "convert_to_task"
}

// --- Portfolio --------------------------------------------------------------
export interface Holding {
  ticker: string
  name: string
  type: string
  quantity?: number | null
  avg_cost?: number | null
  current_price?: number | null
  market_value?: number | null
  pnl_since_bought_pct?: number | null
  pnl_ytd_pct?: number | null
  pnl_last_week_pct?: number | null
  currency: string
}

export interface PortfolioSnapshot {
  total_value: number
  position_count: number
  last_snapshot_date?: string | null
  holdings: Record<string, unknown>[]
}

// --- Money ------------------------------------------------------------------
export interface MoneySnapshot {
  cash_balance?: number | null
  net_worth?: number | null
  net_worth_breakdown: Record<string, unknown>
  monthly_burn?: number | null
  runway_months?: number | null
}

export interface TaxScenarioRequest {
  scenario_description: string
  save_to_project?: string | null
}

// --- Watchlist --------------------------------------------------------------
export interface WatchlistAddRequest {
  ticker: string
  name?: string
  status?: string
  notes?: string
  tier?: string
}

export interface WatchlistHypothesisRequest {
  hypothesis: string
}

// --- Brand ------------------------------------------------------------------
export interface BrandVideoCreateRequest {
  title: string
  platform: string
  concept?: string
}

export interface BrandSkillRequest {
  skill: string // e.g. "generate_hook_variants"
  question?: string | null // only for ask_claude_about_video
}

// --- Career -----------------------------------------------------------------
export interface CareerSkillRequest {
  skill: string // quiz_technicals / mock_interview / deal_note / ...
  arg?: string | null
  context?: string | null // for career_letter_draft
}

export type CareerChecklist = "onboarding" | "technicals"

export interface CareerChecklistToggleRequest {
  checklist: CareerChecklist
  index: number
}

// --- Background runs --------------------------------------------------------
export interface RunStatus {
  run_id: string
  label?: string | null
  status: string
  started_at?: string | null
  completed_at?: string | null
  failed_at?: string | null
  log_file?: string | null
  result?: string | null
  error?: string | null
  detail?: string | null
}

export interface RunLaunchResponse {
  run_id: string
  pid?: number | null
  label: string
  log_file?: string | null
  status_file?: string | null
  launched_at?: string | null
}

// --- Skills -----------------------------------------------------------------
export interface SkillRunRequest {
  args?: Record<string, unknown>
  label?: string | null
}

// --- Search -----------------------------------------------------------------
export interface SearchResult {
  relative_path: string
  snippet: string
  match_count: number
  mtime?: string | null
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
}
