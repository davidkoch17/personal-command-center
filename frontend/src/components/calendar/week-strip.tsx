import type { CalendarEvent } from "@/hooks/useCalendar"
import { eventDateTime } from "./calendar-event"
import { isoDate } from "@/lib/utils"
import { cn } from "@/lib/utils"

const DOW = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]

/**
 * Horizontal 7-day strip; events bucketed by start date.
 *
 * `start` picks the window: `"today"` = rolling 7 days from today (Calendar
 * page), `"monday"` = the current Mo–Su calendar week (Home GROUND zone,
 * Home_Redesign_Spec.md §3a). Today's column is highlighted in both modes.
 */
export function WeekStrip({
  events,
  onSelect,
  start = "today",
}: {
  events: CalendarEvent[]
  onSelect?: (event: CalendarEvent) => void
  start?: "today" | "monday"
}) {
  const today = new Date()
  const first = new Date(today)
  if (start === "monday") {
    // getDay(): Sun=0 … Sat=6 → days since Monday.
    first.setDate(today.getDate() - ((today.getDay() + 6) % 7))
  }
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(first)
    d.setDate(first.getDate() + i)
    return d
  })
  const todayKey = isoDate(today)

  const byDate = new Map<string, CalendarEvent[]>()
  for (const e of events) {
    const key = eventDateTime(e.start).date
    if (!key) continue
    if (!byDate.has(key)) byDate.set(key, [])
    byDate.get(key)!.push(e)
  }

  return (
    <div className="grid grid-cols-7 gap-2">
      {days.map((d) => {
        const key = isoDate(d)
        const dayEvents = byDate.get(key) ?? []
        return (
          <div
            key={key}
            className={cn(
              "flex min-h-[7rem] flex-col rounded-sm border border-border bg-bg-panel/40 p-2",
              key === todayKey && "border-accent-dim/50",
            )}
          >
            <div className="mb-1 flex items-baseline justify-between">
              <span className="label">{DOW[d.getDay()]}</span>
              <span className="font-mono text-xs text-text-secondary">{key.slice(5)}</span>
            </div>
            <div className="flex flex-col gap-1">
              {dayEvents.length === 0 ? (
                <span className="text-xs text-text-label">—</span>
              ) : (
                dayEvents.map((e, j) => (
                  <button
                    key={j}
                    type="button"
                    onClick={() => onSelect?.(e)}
                    className="truncate rounded-sm bg-accent-soft/40 px-1.5 py-0.5 text-left text-xs text-text hover:bg-accent-soft"
                  >
                    {eventDateTime(e.start).time} {e.title}
                  </button>
                ))
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
