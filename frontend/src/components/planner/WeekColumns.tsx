import { useDroppable, useDraggable } from "@dnd-kit/core"
import { GripVertical, X } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  DAY_KEYS,
  dayLabel,
  dayDateLabel,
  isToday,
  weekDates,
  type WeekData,
  type CalendarOverlay,
  type Assignment,
  type DayKey,
  type PoolTask,
} from "@/lib/planner"

interface WeekColumnsProps {
  week: WeekData
  calendar: CalendarOverlay
  isoWeek: string
  readOnly: boolean
  openIds: Set<string>
  poolById: Map<string, PoolTask>
  onToggle: (taskId: string) => void
  onRemove: (taskId: string) => void
}

/**
 * The left 60% — seven day columns, each a drop zone for tasks. Each header
 * shows the weekday + date with a calendar-overlay line beneath. The current
 * day gets an accent ring. Past weeks render read-only (no drag handles, no
 * remove buttons).
 */
export function WeekColumns({
  week,
  calendar,
  isoWeek,
  readOnly,
  openIds,
  poolById,
  onToggle,
  onRemove,
}: WeekColumnsProps) {
  const dates = weekDates(isoWeek)
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-7">
      {DAY_KEYS.map((dayKey, i) => (
        <DayColumn
          key={dayKey}
          dayKey={dayKey}
          date={dates[i]}
          entries={week[dayKey] ?? []}
          events={calendar[dayKey] ?? []}
          readOnly={readOnly}
          openIds={openIds}
          poolById={poolById}
          onToggle={onToggle}
          onRemove={onRemove}
        />
      ))}
    </div>
  )
}

function DayColumn({
  dayKey,
  date,
  entries,
  events,
  readOnly,
  openIds,
  poolById,
  onToggle,
  onRemove,
}: {
  dayKey: DayKey
  date: Date
  entries: Assignment[]
  events: CalendarOverlay[DayKey]
  readOnly: boolean
  openIds: Set<string>
  poolById: Map<string, PoolTask>
  onToggle: (taskId: string) => void
  onRemove: (taskId: string) => void
}) {
  const { setNodeRef, isOver } = useDroppable({ id: dayKey, disabled: readOnly })
  const today = isToday(date)
  const sorted = [...entries].sort((a, b) => (a.order ?? 0) - (b.order ?? 0))

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex min-h-[180px] flex-col rounded-lg border bg-bg-panel transition-colors",
        today ? "border-accent" : "border-border",
        isOver && "border-accent-dim bg-bg-panel-hover ring-1 ring-accent-dim",
      )}
    >
      {/* Sticky header with calendar overlay */}
      <div
        className={cn(
          "sticky top-0 z-10 rounded-t-lg border-b border-border bg-bg-panel px-3 py-2",
          today && "bg-accent-soft/20",
        )}
      >
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-sm font-medium text-text">
            {dayLabel(dayKey)}{" "}
            <span className="font-mono text-xs text-text-secondary tabular-nums">
              ({dayDateLabel(date)})
            </span>
          </span>
          {today && (
            <span className="text-[10px] uppercase tracking-wider text-accent">today</span>
          )}
        </div>
        {events && events.length > 0 && (
          <div className="mt-1 truncate font-mono text-[10px] text-text-label">
            {events.map((e) => `${e.start} ${e.title}`.trim()).join(" · ")}
          </div>
        )}
      </div>

      {/* Task list */}
      <div className="flex flex-1 flex-col gap-1.5 p-2">
        {sorted.length === 0 ? (
          <p className="px-1 py-2 text-xs text-text-label">
            {readOnly ? "—" : "drop tasks here"}
          </p>
        ) : (
          sorted.map((entry) => (
            <DayTaskCard
              key={entry.task_id}
              entry={entry}
              done={!openIds.has(entry.task_id)}
              readOnly={readOnly}
              fallbackText={poolById.get(entry.task_id)?.text}
              onToggle={() => onToggle(entry.task_id)}
              onRemove={() => onRemove(entry.task_id)}
            />
          ))
        )}
      </div>
    </div>
  )
}

function DayTaskCard({
  entry,
  done,
  readOnly,
  fallbackText,
  onToggle,
  onRemove,
}: {
  entry: Assignment
  done: boolean
  readOnly: boolean
  fallbackText?: string
  onToggle: () => void
  onRemove: () => void
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: entry.task_id,
    disabled: readOnly,
  })
  const text = entry.text ?? fallbackText
  const orphaned = !text

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "group flex items-start gap-1.5 rounded-md border border-border bg-bg px-1.5 py-1.5",
        isDragging && "opacity-40",
      )}
    >
      {!readOnly && (
        <button
          type="button"
          className="mt-0.5 shrink-0 cursor-grab text-text-disabled hover:text-text-secondary active:cursor-grabbing"
          {...attributes}
          {...listeners}
          aria-label="drag task"
        >
          <GripVertical className="h-3.5 w-3.5" />
        </button>
      )}
      {/* Completion dot */}
      <button
        type="button"
        disabled={readOnly}
        onClick={onToggle}
        aria-label={done ? "mark open" : "mark done"}
        className={cn(
          "mt-1 h-3 w-3 shrink-0 rounded-full border transition-colors disabled:cursor-not-allowed",
          done ? "border-accent bg-accent" : "border-text-label hover:border-text-secondary",
        )}
      />
      <div className="min-w-0 flex-1">
        <span
          className={cn(
            "block text-xs leading-snug",
            done ? "text-text-secondary line-through" : "text-text",
            orphaned && "italic text-warning",
          )}
        >
          {text ?? "(removed from source)"}
        </span>
        {entry.source_label && (
          <span className="mt-0.5 block truncate font-mono text-[10px] text-text-label">
            {entry.source_label}
          </span>
        )}
        {orphaned && !readOnly && (
          <button
            type="button"
            onClick={onRemove}
            className="mt-0.5 text-[10px] text-warning underline hover:text-text"
          >
            remove from planner
          </button>
        )}
      </div>
      {!readOnly && !orphaned && (
        <button
          type="button"
          onClick={onRemove}
          aria-label="remove from planner"
          className="mt-0.5 shrink-0 text-text-disabled opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
}
