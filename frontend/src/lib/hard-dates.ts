/**
 * HARD DATES — the immovable real-world deadlines David wants always in view.
 *
 * Hardcoded for now (Phase 12b). These are placeholders David should edit to the
 * real dates; the Home strip computes a live countdown from `date` (ISO
 * YYYY-MM-DD). A later phase can source these from the vault instead.
 *
 * TODO(david): confirm each date below.
 */
export interface HardDate {
  label: string
  date: string // ISO YYYY-MM-DD
}

export const HARD_DATES: HardDate[] = [
  { label: "ffm apartment", date: "2026-07-01" },
  { label: "credit cards due", date: "2026-06-15" },
  { label: "defense", date: "2026-06-20" },
  { label: "miami", date: "2026-08-10" },
  { label: "evercore start", date: "2026-09-01" },
]
