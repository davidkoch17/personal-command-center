import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

/** One NOW-zone focus area card (Home_Redesign_Spec.md §1a). */
export interface FocusArea {
  key: string
  title: string
  status: "green" | "yellow" | "red"
  next_action: string
  time_indicator: string | null
  target: string
  new_tab: boolean
}

export interface WatchlistSignalsResponse {
  brief_date: string | null
  age_days: number | null
  signals: string[]
}

export interface NotgroschenResponse {
  phase: 1 | 2
  cash_balance: number | null
  target: number
  pct: number | null
  depot_invested: number | null
}

export interface TasksSummaryResponse {
  open: number
  high_priority: number
  top: { text: string; section: string }[]
}

/** One Skills & Agents directory row (Home_Redesign_Spec.md §3c). */
export interface SkillStatus {
  key: string
  label: string
  status: "ok" | "due" | "failed" | "never"
  last_run_at: string | null
  last_run_id: string | null
  last_run_status: string | null
  run_skill: string | null
  prompt_arg: string | null
  run_target: string | null
  note: string | null
}

/** Brain/System card payload (Brain_System_Card_Spec.md) — all sources nullable. */
export interface BrainSystemResponse {
  pending_upgrades: {
    count: number
    top: { id: string; title: string }[]
  } | null
  reading: {
    current_book: string
    started: string | null
    last_read: string | null
    progress: string | null
    stale_days: number | null
  } | null
  weekly_review: {
    last_review_date: string | null
    days_since: number | null
    next_due: string
    days_until_next: number
    overdue: boolean
  }
}

export function useBrainSystem() {
  return useQuery({
    queryKey: ["home", "brain-system"],
    queryFn: () => api.get<BrainSystemResponse>("/api/home/brain-system"),
    staleTime: 5 * 60_000,
  })
}

/** One "Awaiting your input" row (Manual_Tasks_Card_Spec.md). */
export interface ManualTask {
  id: string
  title: string
  what: string
  file_path: string
  section: string
  why: string
  estimated_time: string
  priority: "low" | "medium" | "high"
  /** Pre-fill for the in-app editor when the target file doesn't exist yet. */
  template?: string | null
}

export interface ManualTasksResponse {
  tasks: ManualTask[]
  all_clear: boolean
}

export function useManualTasks() {
  return useQuery({
    queryKey: ["home", "manual-tasks"],
    queryFn: () => api.get<ManualTasksResponse>("/api/home/manual-tasks"),
    staleTime: 5 * 60_000,
  })
}

export function useFocusAreas() {
  return useQuery({
    queryKey: ["home", "focus-areas"],
    queryFn: () => api.get<{ cards: FocusArea[] }>("/api/home/focus-areas"),
    staleTime: 5 * 60_000,
  })
}

export function useWatchlistSignals() {
  return useQuery({
    queryKey: ["home", "watchlist-signals"],
    queryFn: () => api.get<WatchlistSignalsResponse>("/api/home/watchlist-signals"),
    staleTime: 10 * 60_000,
  })
}

export function useNotgroschen() {
  return useQuery({
    queryKey: ["home", "notgroschen"],
    queryFn: () => api.get<NotgroschenResponse>("/api/home/notgroschen"),
    staleTime: 5 * 60_000,
  })
}

export function useTasksSummary() {
  return useQuery({
    queryKey: ["home", "tasks-summary"],
    queryFn: () => api.get<TasksSummaryResponse>("/api/home/tasks-summary"),
  })
}

export function useSkillsStatus() {
  return useQuery({
    queryKey: ["skills", "status"],
    queryFn: () => api.get<{ skills: SkillStatus[] }>("/api/skills/status"),
    staleTime: 60_000,
  })
}
