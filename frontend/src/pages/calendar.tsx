import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { CalendarEventCard, eventDateTime } from "@/components/calendar/calendar-event"
import { WeekStrip } from "@/components/calendar/week-strip"
import { useCalendar, type CalendarEvent } from "@/hooks/useCalendar"

export function Calendar() {
  const { data, isLoading, isError } = useCalendar(30)
  const [selected, setSelected] = useState<CalendarEvent | null>(null)

  const events = data?.events ?? []
  const next5 = events.slice(0, 5)

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">calendar</h1>

      {isError && (
        <Panel title="error" statusDotColor="danger">
          <p className="text-text-secondary">could not load calendar. backend on :8000?</p>
        </Panel>
      )}

      {isLoading ? (
        <Skeleton className="h-40" />
      ) : !data?.configured ? (
        <Panel title="calendar" statusDotColor="muted">
          <p className="text-sm text-text-secondary">
            calendar not configured. see setup guide in vault:{" "}
            <span className="font-mono text-xs text-text">
              99_System/Credentials_Setup_Guide.md
            </span>
          </p>
        </Panel>
      ) : (
        <>
          {/* Next 5 */}
          <Panel title="next 5 events" meta={`${events.length} in 30d`} statusDotColor="accent">
            {next5.length === 0 ? (
              <p className="text-sm text-text-label">no upcoming events</p>
            ) : (
              <div className="space-y-2">
                {next5.map((e, i) => (
                  <CalendarEventCard key={i} event={e} large onClick={() => setSelected(e)} />
                ))}
              </div>
            )}
          </Panel>

          {/* Week strip */}
          <Panel title="this week" statusDotColor="muted">
            <WeekStrip events={events} onSelect={setSelected} />
          </Panel>
        </>
      )}

      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{selected?.title}</DialogTitle>
          </DialogHeader>
          {selected && (
            <div className="space-y-2 text-sm">
              <Detail label="start" value={`${eventDateTime(selected.start).date} ${eventDateTime(selected.start).time}`} />
              <Detail label="end" value={`${eventDateTime(selected.end).date} ${eventDateTime(selected.end).time}`} />
              {selected.location && <Detail label="location" value={selected.location} />}
              {selected.description && (
                <div>
                  <div className="label mb-1">description</div>
                  <p className="whitespace-pre-wrap text-text-secondary">{selected.description}</p>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-3">
      <span className="label w-20 shrink-0">{label}</span>
      <span className="font-mono text-xs text-text">{value}</span>
    </div>
  )
}
