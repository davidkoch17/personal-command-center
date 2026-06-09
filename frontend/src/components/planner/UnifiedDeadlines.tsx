import { AlarmClock } from "lucide-react"
import { useHardDates } from "@/hooks/useTasks"
import {
  countdownLabel,
  daysUntil,
  deadlineUrgency,
  formatAbsoluteDate,
  urgencyColor,
} from "@/lib/status"
import { InlineMd } from "@/components/ui/inline-markdown"
import { cn } from "@/lib/utils"

/**
 * Hard deadlines for the Plan page's Today strip with the v2 unified display:
 * absolute + relative + urgency, e.g. "Mon 8 Jun · in 3d · high".
 * Reads the "Hard dates locked" block of Task_Command_Center.md.
 */
export function UnifiedDeadlines({ horizonDays = 14 }: { horizonDays?: number }) {
  const { data } = useHardDates()
  const upcoming = (data ?? [])
    .filter((d) => {
      const days = daysUntil(d.date)
      return days !== null && days >= 0 && days <= horizonDays
    })
    // Backend already date-sorts, but be defensive.
    .sort((a, b) => (daysUntil(a.date) ?? 0) - (daysUntil(b.date) ?? 0))

  return (
    <div className="rounded-lg border border-border bg-bg-panel">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <AlarmClock className="h-3.5 w-3.5 shrink-0 text-accent" />
        <span className="label">hard deadlines</span>
        <span className="ml-auto font-mono text-[10px] text-text-label">
          next {horizonDays}d
        </span>
      </div>
      {upcoming.length === 0 ? (
        <p className="px-3 py-3 text-sm text-text-label">no hard deadlines ahead.</p>
      ) : (
        <ul className="divide-y divide-border">
          {upcoming.map((d) => {
            const urgency = deadlineUrgency(d.date)
            return (
              <li
                key={`${d.date}-${d.label}`}
                className="flex items-baseline justify-between gap-3 px-3 py-2"
              >
                <span className="min-w-0 truncate text-sm text-text">
                  <InlineMd text={d.label} />
                </span>
                <span className="flex shrink-0 items-baseline gap-2 font-mono text-xs tabular-nums">
                  <span className="text-text-secondary">{formatAbsoluteDate(d.date)}</span>
                  <span className="text-text-label">·</span>
                  <span className={urgencyColor(urgency)}>{countdownLabel(d.date)}</span>
                  <span className="text-text-label">·</span>
                  <span
                    className={cn(
                      "rounded-sm px-1.5 text-[10px] font-medium uppercase tracking-wider",
                      urgency === "high" || urgency === "overdue"
                        ? "bg-danger/15 text-danger"
                        : urgency === "medium"
                          ? "bg-warning/15 text-warning"
                          : "bg-accent-soft text-accent",
                    )}
                  >
                    {urgency}
                  </span>
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
