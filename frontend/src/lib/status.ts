import type { StatusColor } from "@/components/ui/status-dot"
import type { ProjectStatus } from "@/lib/types"

/** Map a backend project status to a semantic dot color + lowercase label. */
export function projectStatusMeta(status: ProjectStatus): {
  color: StatusColor
  label: string
} {
  switch (status) {
    case "on_track":
      return { color: "success", label: "on track" }
    case "needs_attention":
      return { color: "warning", label: "needs attention" }
    case "at_risk":
      return { color: "danger", label: "at risk" }
    case "done":
      return { color: "accent", label: "done" }
    default:
      return { color: "muted", label: "unknown" }
  }
}

/**
 * Whole-day countdown to an ISO date (negative = past). Returns null for a
 * missing/invalid date.
 */
export function daysUntil(isoDateStr?: string | null): number | null {
  if (!isoDateStr) return null
  const target = new Date(isoDateStr)
  if (Number.isNaN(target.getTime())) return null
  const today = new Date()
  const a = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())
  const b = Date.UTC(target.getFullYear(), target.getMonth(), target.getDate())
  return Math.round((b - a) / 86_400_000)
}

/** Humanize a day delta: "in 5d", "today", "2d ago". */
export function countdownLabel(isoDateStr?: string | null): string | null {
  const d = daysUntil(isoDateStr)
  if (d === null) return null
  if (d === 0) return "today"
  if (d > 0) return `in ${d}d`
  return `${Math.abs(d)}d ago`
}

/** Absolute deadline label, e.g. "Mon 8 Jun". Empty string for a bad date. */
export function formatAbsoluteDate(isoDateStr?: string | null): string {
  if (!isoDateStr) return ""
  const d = new Date(isoDateStr)
  if (Number.isNaN(d.getTime())) return ""
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })
}

export type Urgency = "overdue" | "high" | "medium" | "low"

/**
 * Deadline urgency for the unified deadline display: overdue (past), high
 * (≤2d), medium (≤5d), low (further out). Drives the color + word badge.
 */
export function deadlineUrgency(isoDateStr?: string | null): Urgency {
  const d = daysUntil(isoDateStr)
  if (d === null) return "low"
  if (d < 0) return "overdue"
  if (d <= 2) return "high"
  if (d <= 5) return "medium"
  return "low"
}

/** Tailwind text-color class for an urgency level. */
export function urgencyColor(u: Urgency): string {
  switch (u) {
    case "overdue":
    case "high":
      return "text-danger"
    case "medium":
      return "text-warning"
    default:
      return "text-accent"
  }
}
