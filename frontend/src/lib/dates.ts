/**
 * Deadline formatting helpers — show BOTH a relative countdown and the absolute
 * ISO date wherever a deadline appears (e.g. "in 5d · 2026-06-20").
 *
 * Built on the existing whole-day countdown logic in `status.ts` (local-time,
 * no UTC off-by-one) so the wording matches the rest of the app.
 */
import { countdownLabel } from "@/lib/status"
import { isoDate } from "@/lib/utils"

/** Relative day countdown: "today" / "in 5d" / "2d ago" ("" if unparseable). */
export function formatRelative(target: string | Date): string {
  const iso = typeof target === "string" ? target : isoDate(target)
  return countdownLabel(iso) ?? ""
}

/** Absolute date as `YYYY-MM-DD`. */
export function formatDateISO(target: string | Date): string {
  if (typeof target === "string") {
    // Already ISO-ish: take the date portion. Otherwise parse, then format local.
    if (/^\d{4}-\d{2}-\d{2}/.test(target)) return target.slice(0, 10)
    const parsed = new Date(target)
    return Number.isNaN(parsed.getTime()) ? target : isoDate(parsed)
  }
  return isoDate(target)
}

/** Both at once: "in 5d · 2026-06-20" (falls back to just the date). */
export function formatBoth(target: string | Date): string {
  const rel = formatRelative(target)
  const abs = formatDateISO(target)
  return rel ? `${rel} · ${abs}` : abs
}
