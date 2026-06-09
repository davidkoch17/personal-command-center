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

/** Plan-page task tags (mirrors the Task_Command_Center.md convention). */
export const TASK_TAGS = ["quick", "deep-work", "busy"] as const
export type TaskTag = (typeof TASK_TAGS)[number]
/** Tags surfaced in the bottom busy-task bar (quick-grab, <1h work). */
export const BUSY_TAGS: readonly TaskTag[] = ["quick", "busy"]

export interface PoolTask {
  id: string
  text: string
  source_path: string
  source_label: string
  source_section: string
  line_index: number | null
  is_completed: boolean
  is_carry_forward?: boolean
  tags?: TaskTag[]
}

/** One assignment within a day. Text/source are cached for render-after-done. */
export interface Assignment {
  task_id: string
  order: number
  text?: string
  source_label?: string
}

/**
 * A deep-work block (NEW in v2) — a project-tagged time reservation dropped on a
 * day, distinct from a task. Stored under ``week.blocks[day]`` so the backend's
 * task-only day arrays (pool / stats) are never touched by blocks.
 */
export interface DeepWorkBlock {
  id: string
  project: string
  title?: string
  duration_min: number
  color: string
}

export type WeekBlocks = Partial<Record<DayKey, DeepWorkBlock[]>>

export type WeekData = {
  iso_week: string
  last_modified: string | null
  blocks?: WeekBlocks
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

// --- Task tags --------------------------------------------------------------

const TAG_RE = /#(quick|deep-work|busy)\b/gi

/** Recognised Plan tags found in a task line (canonical-cased, deduped). */
export function parseTags(text: string): TaskTag[] {
  const found = new Set<string>()
  for (const m of text.matchAll(TAG_RE)) found.add(m[1].toLowerCase())
  return TASK_TAGS.filter((t) => found.has(t))
}

/** Task text with recognised tag hashtags stripped, for clean display. */
export function stripTags(text: string): string {
  return text.replace(TAG_RE, "").replace(/\s{2,}/g, " ").trim()
}

/** A task's tags, preferring server-provided list, falling back to its text. */
export function tagsOf(task: PoolTask): TaskTag[] {
  return task.tags && task.tags.length ? task.tags : parseTags(task.text)
}

// --- Deep-work block color (stable, derived from the project name) ----------

const BLOCK_PALETTE = [
  "#6366F1", // indigo
  "#10B981", // emerald
  "#F59E0B", // amber
  "#EC4899", // pink
  "#06B6D4", // cyan
  "#8B5CF6", // violet
  "#EF4444", // red
  "#84CC16", // lime
]

/** Deterministic palette color for a project string (same project → same hue). */
export function blockColor(project: string): string {
  let h = 0
  const s = project.trim().toLowerCase()
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return BLOCK_PALETTE[h % BLOCK_PALETTE.length]
}

/** Common project tags offered in the deep-work block creator (free-typeable). */
export const BLOCK_PROJECTS = [
  "Evercore",
  "Thesis",
  "K&E",
  "Acebuche",
  "Investing",
  "Brand",
  "Admin",
] as const

/** Humanize a minute duration: 90 → "1h30", 60 → "1h", 30 → "30m". */
export function formatDuration(min: number): string {
  if (min < 60) return `${min}m`
  const h = Math.floor(min / 60)
  const m = min % 60
  return m === 0 ? `${h}h` : `${h}h${String(m).padStart(2, "0")}`
}

// --- Month math (for the secondary month tab) -------------------------------

/** First day of the month for an ISO week's Monday (uses mid-week to be safe). */
export function monthOfIsoWeek(isoWeek: string): Date {
  const dates = weekDates(isoWeek)
  const mid = dates[3] // Thursday — always in the ISO week's "owning" month-ish
  return new Date(mid.getFullYear(), mid.getMonth(), 1)
}

/** Shift a month-anchor Date by ±n months. */
export function addMonths(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + n, 1)
}

/** "June 2026" label for a month anchor. */
export function monthLabel(d: Date): string {
  return d.toLocaleDateString("en-GB", { month: "long", year: "numeric" })
}

/**
 * The calendar matrix for a month: full weeks (Mon–Sun) covering every day of
 * the month, padded with neighbouring-month days so each row has 7 entries.
 */
export function monthMatrix(anchor: Date): Date[][] {
  const year = anchor.getFullYear()
  const month = anchor.getMonth()
  const first = new Date(year, month, 1)
  const startOffset = (first.getDay() + 6) % 7 // Mon=0
  const gridStart = new Date(year, month, 1 - startOffset)
  const weeks: Date[][] = []
  const cursor = new Date(gridStart)
  // 6 rows max covers any month layout; trim trailing all-next-month rows.
  for (let w = 0; w < 6; w++) {
    const row: Date[] = []
    for (let d = 0; d < 7; d++) {
      row.push(new Date(cursor))
      cursor.setDate(cursor.getDate() + 1)
    }
    weeks.push(row)
    if (cursor.getMonth() !== month && cursor > first) {
      // Stop once we've passed the month and filled the week containing its end.
      if (row.some((dd) => dd.getMonth() === month) === false && w >= 4) break
    }
  }
  return weeks
}
