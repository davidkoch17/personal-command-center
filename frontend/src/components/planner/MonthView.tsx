import { useMemo, useState } from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { isoDate } from "@/lib/utils"
import {
  addMonths,
  dateToIsoWeek,
  isToday,
  monthLabel,
  monthMatrix,
  monthOfIsoWeek,
} from "@/lib/planner"
import type { CalendarEvent } from "@/hooks/useCalendar"

interface MonthViewProps {
  isoWeek: string
  events: CalendarEvent[]
  /** Jump to the week view containing the clicked day. */
  onPickWeek: (isoWeek: string) => void
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

/**
 * Secondary month tab — a calendar-style month grid for longer-horizon planning.
 * Overlays iCal events per day; clicking a day jumps to that week in the week
 * view. Most work still happens in the week view; this is the wide-angle lens.
 */
export function MonthView({ isoWeek, events, onPickWeek }: MonthViewProps) {
  const [anchor, setAnchor] = useState<Date>(() => monthOfIsoWeek(isoWeek))
  const month = anchor.getMonth()
  const weeks = useMemo(() => monthMatrix(anchor), [anchor])

  // Bucket events by YYYY-MM-DD of their start.
  const byDay = useMemo(() => {
    const m = new Map<string, CalendarEvent[]>()
    for (const e of events) {
      if (!e.start) continue
      const key = e.start.slice(0, 10)
      const list = m.get(key) ?? []
      list.push(e)
      m.set(key, list)
    }
    return m
  }, [events])

  return (
    <div className="rounded-lg border border-border bg-bg-panel">
      <div className="flex items-center justify-between gap-3 border-b border-border px-3 py-2.5">
        <span className="text-sm font-medium text-text">{monthLabel(anchor)}</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setAnchor((a) => addMonths(a, -1))}
            aria-label="previous month"
            className="text-text-secondary hover:text-text"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={() => setAnchor(monthOfIsoWeek(isoWeek))}
            className="text-xs text-text-secondary hover:text-text"
          >
            today
          </button>
          <button
            type="button"
            onClick={() => setAnchor((a) => addMonths(a, 1))}
            aria-label="next month"
            className="text-text-secondary hover:text-text"
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 border-b border-border">
        {WEEKDAYS.map((d) => (
          <div
            key={d}
            className="px-2 py-1.5 text-center font-mono text-[10px] uppercase tracking-wider text-text-label"
          >
            {d}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7">
        {weeks.flat().map((date, i) => {
          const inMonth = date.getMonth() === month
          const dayEvents = byDay.get(isoDate(date)) ?? []
          const today = isToday(date)
          return (
            <button
              key={i}
              type="button"
              onClick={() => onPickWeek(dateToIsoWeek(date))}
              className={cn(
                "flex min-h-[88px] flex-col items-stretch gap-1 border-b border-r border-border p-1.5 text-left transition-colors hover:bg-bg-panel-hover",
                (i + 1) % 7 === 0 && "border-r-0",
                !inMonth && "bg-bg/40",
              )}
            >
              <span
                className={cn(
                  "self-end font-mono text-[11px] tabular-nums",
                  today
                    ? "rounded-full bg-accent px-1.5 text-bg"
                    : inMonth
                      ? "text-text-secondary"
                      : "text-text-disabled",
                )}
              >
                {date.getDate()}
              </span>
              <div className="flex flex-col gap-0.5">
                {dayEvents.slice(0, 3).map((e, j) => (
                  <span
                    key={j}
                    className="truncate rounded-sm bg-accent-soft/40 px-1 text-[10px] text-text-secondary"
                    title={e.title}
                  >
                    {e.title}
                  </span>
                ))}
                {dayEvents.length > 3 && (
                  <span className="px-1 text-[10px] text-text-label">
                    +{dayEvents.length - 3} more
                  </span>
                )}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
