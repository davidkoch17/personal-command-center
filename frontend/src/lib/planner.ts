/**
 * Week Planner shared types + ISO-week date math (Phase 16).
 *
 * Storage model: the planner JSON holds only ASSIGNMENT — which task lands on
 * which day. Each assignment caches ``text`` + ``source_label`` so a day column
 * can render a task even after it has been checked off and left the open pool.
 * Completion state itself always lives in the source markdown.
 */

export const DAY_KEYS = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
] as const

export type DayKey = (typeof DAY_KEYS)[number]

const DAY_LABELS: Record<DayKey, string> = {
  monday: "Monday",
  tuesday: "Tuesday",
  wednesday: "Wednesday",
  thursday: "Thursday",
  friday: "Friday",
  saturday: "Saturday",
  sunday: "Sunday",
}

export interface PoolTask {
  id: string
  text: string
  source_path: string
  source_label: string
  source_section: string
  line_index: number | null
  is_completed: boolean
  is_carry_forward?: boolean
}

/** One assignment within a day. Text/source are cached for render-after-done. */
export interface Assignment {
  task_id: string
  order: number
  text?: string
  source_label?: string
}

export type WeekData = {
  iso_week: string
  last_modified: string | null
} & Record<DayKey, Assignment[]>

export interface DayEvent {
  title: string
  start: string
  is_all_day: boolean
}

export type CalendarOverlay = Partial<Record<DayKey, DayEvent[]>>

export interface WeekStats {
  total: number
  done: number
  percentage: number
  done_tasks: { id: string; day: string; text: string }[]
}

export interface PoolResponse {
  pool: PoolTask[]
  open_ids: string[]
  total_open: number
  assigned_count: number
}

export interface WeekResponse {
  week: WeekData
  calendar: CalendarOverlay
  stats: WeekStats
}

export interface AIRecommendation {
  task_id: string
  task_text: string
  suggested_day: DayKey | "later" | string
  rationale?: string
}

export interface AIRecommendResponse {
  recommendations: AIRecommendation[]
  warnings?: string[]
  summary?: string
}

// --- ISO-week math (local time; no UTC off-by-one) --------------------------

/** ISO week string ("YYYY-Www") for a given local date. */
export function dateToIsoWeek(d: Date): string {
  // Shift to the Thursday of the current ISO week, then count weeks from the
  // year's first Thursday (the standard ISO-8601 algorithm).
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const dayNr = (target.getDay() + 6) % 7 // Mon=0 .. Sun=6
  target.setDate(target.getDate() - dayNr + 3)
  const isoYear = target.getFullYear()
  const firstThursday = new Date(isoYear, 0, 4)
  const ftDayNr = (firstThursday.getDay() + 6) % 7
  firstThursday.setDate(firstThursday.getDate() - ftDayNr + 3)
  const week = 1 + Math.round((target.getTime() - firstThursday.getTime()) / (7 * 86400000))
  return `${isoYear}-W${String(week).padStart(2, "0")}`
}

/** The Monday (local midnight) of a given ISO week string. */
export function isoWeekToMonday(isoWeek: string): Date {
  const [yStr, wStr] = isoWeek.split("-W")
  const year = Number(yStr)
  const week = Number(wStr)
  const jan4 = new Date(year, 0, 4)
  const jan4Day = (jan4.getDay() + 6) % 7
  const week1Monday = new Date(jan4)
  week1Monday.setDate(jan4.getDate() - jan4Day)
  const monday = new Date(week1Monday)
  monday.setDate(week1Monday.getDate() + (week - 1) * 7)
  return monday
}

/** The current ISO week string. */
export function getCurrentIsoWeek(): string {
  return dateToIsoWeek(new Date())
}

/** Previous / next ISO week string. */
export function prevWeek(isoWeek: string): string {
  const m = isoWeekToMonday(isoWeek)
  m.setDate(m.getDate() - 7)
  return dateToIsoWeek(m)
}
export function nextWeek(isoWeek: string): string {
  const m = isoWeekToMonday(isoWeek)
  m.setDate(m.getDate() + 7)
  return dateToIsoWeek(m)
}

/** The 7 dates (Mon..Sun) of an ISO week, as Date objects. */
export function weekDates(isoWeek: string): Date[] {
  const monday = isoWeekToMonday(isoWeek)
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    return d
  })
}

/** Map a Date to its day key (monday..sunday). */
export function dayKeyOf(d: Date): DayKey {
  return DAY_KEYS[(d.getDay() + 6) % 7]
}

export function dayLabel(key: DayKey): string {
  return DAY_LABELS[key]
}

/** Compact "DD.MM" date label used in day headers. */
export function dayDateLabel(d: Date): string {
  const dd = String(d.getDate()).padStart(2, "0")
  const mm = String(d.getMonth() + 1).padStart(2, "0")
  return `${dd}.${mm}`
}

/** True if the given date is today (local). */
export function isToday(d: Date): boolean {
  const now = new Date()
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  )
}

/** Every task_id assigned somewhere in the week. */
export function getAllAssignedIds(week: WeekData | null): string[] {
  if (!week) return []
  const ids: string[] = []
  for (const day of DAY_KEYS) {
    for (const entry of week[day] ?? []) ids.push(entry.task_id)
  }
  return ids
}

/** Is `isoWeek` strictly before the current week? (lexical compare is safe). */
export function isPastWeek(isoWeek: string): boolean {
  return isoWeek < getCurrentIsoWeek()
}
