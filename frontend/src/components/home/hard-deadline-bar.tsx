import { AlarmClock } from "lucide-react"
import { useHardDates } from "@/hooks/useTasks"
import { countdownLabel, daysUntil } from "@/lib/status"
import { cn } from "@/lib/utils"

/**
 * Hard deadlines strip below the focus areas (Home_Redesign_Spec.md §1b):
 * this week's immovable dates with countdowns, e.g.
 * "⏰ Defense in 3d · Ulli draft in 2d · Credit cards today".
 * Reads the "Hard dates locked" block of Task_Command_Center.md.
 */
export function HardDeadlineBar() {
  const { data } = useHardDates()
  // Next 14 days (already date-sorted by the backend); past dates age out.
  const upcoming = (data ?? []).filter((d) => {
    const days = daysUntil(d.date)
    return days !== null && days >= 0 && days <= 14
  })
  if (upcoming.length === 0) return null

  return (
    <div className="flex items-center gap-2 overflow-x-auto rounded-sm border border-border bg-bg-panel px-3 py-2">
      <AlarmClock className="h-3.5 w-3.5 shrink-0 text-accent" />
      <div className="flex items-center gap-1 whitespace-nowrap">
        {upcoming.map((d, i) => {
          const days = daysUntil(d.date) ?? 0
          return (
            <span key={`${d.date}-${d.label}`} className="flex items-center gap-1 text-xs">
              {i > 0 && <span className="px-1.5 text-text-label">·</span>}
              <span className="text-text-secondary">{d.label}</span>
              <span
                className={cn(
                  "font-mono tabular-nums",
                  days <= 1 ? "text-warning" : "text-accent",
                )}
              >
                {countdownLabel(d.date)}
              </span>
            </span>
          )
        })}
      </div>
    </div>
  )
}
