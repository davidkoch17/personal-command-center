import { MapPin } from "lucide-react"
import type { CalendarEvent as CalendarEventData } from "@/hooks/useCalendar"

/** Format an ISO datetime into `YYYY-MM-DD` + `HH:MM` parts. */
export function eventDateTime(iso: string | null): { date: string; time: string } {
  if (!iso) return { date: "", time: "" }
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return { date: iso.slice(0, 10), time: "" }
  const date = iso.slice(0, 10)
  const time = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
  return { date, time }
}

interface CalendarEventCardProps {
  event: CalendarEventData
  onClick?: () => void
  large?: boolean
}

/** Event card — date, title, time, location. */
export function CalendarEventCard({ event, onClick, large = false }: CalendarEventCardProps) {
  const { date, time } = eventDateTime(event.start)
  return (
    <button
      type="button"
      onClick={onClick}
      className="panel panel-hover flex w-full items-start justify-between gap-3 text-left transition-colors"
    >
      <div className="min-w-0">
        <div className={large ? "text-base text-text" : "text-sm text-text"}>{event.title}</div>
        {event.location && (
          <div className="mt-0.5 flex items-center gap-1 text-xs text-text-secondary">
            <MapPin className="h-3 w-3" />
            <span className="truncate">{event.location}</span>
          </div>
        )}
      </div>
      <div className="shrink-0 text-right">
        <div className="font-mono text-xs text-accent">{date}</div>
        <div className="font-mono text-xs text-text-secondary">{time}</div>
      </div>
    </button>
  )
}
