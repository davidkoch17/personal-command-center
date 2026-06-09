import { useDroppable, useDraggable } from "@dnd-kit/core"
import { GripVertical, X, CalendarClock } from "lucide-react"
import { cn } from "@/lib/utils"
import { InlineMd } from "@/components/ui/inline-markdown"
import {
  DAY_KEYS,
  dayLabel,
  dayDateLabel,
  isToday,
  weekDates,
  formatDuration,
  stripTags,
  type WeekData,
  type CalendarOverlay,
  type Assignment,
  type DayKey,
  type DayEvent,
  type DeepWorkBlock,
  type PoolTask,
} from "@/lib/planner"

/** dnd id for an existing block on the grid (vs a raw task_id or "newblock"). */
export const BLOCK_ID_PREFIX = "block::"
export const blockDragId = (id: string) => `${BLOCK_ID_PREFIX}${id}`
export const isBlockDragId = (id: string) => id.startsWith(BLOCK_ID_PREFIX)
export const blockIdFromDrag = (id: string) => id.slice(BLOCK_ID_PREFIX.length)

interface PlanWeekGridProps {
  week: WeekData
  calendar: CalendarOverlay
  isoWeek: string
  readOnly: boolean
  openIds: Set<string>
  poolById: Map<string, PoolTask>
  onToggle: (taskId: string) => void
  onRemoveTask: (taskId: string) => void
  onRemoveBlock: (day: DayKey, blockId: string) => void
}

/**
 * The Plan spine — seven Mon–Su day columns. Each column is a drop zone that
 * accepts tasks (from the pool) and deep-work blocks (from the creator). It
 * renders three layers: a non-draggable calendar-event overlay, color-coded
 * deep-work blocks, and task cards. Past weeks render read-only.
 */
export function PlanWeekGrid({
  week,
  calendar,
  isoWeek,
  readOnly,
  openIds,
  poolById,
  onToggle,
  onRemoveTask,
  onRemoveBlock,
}: PlanWeekGridProps) {
  const dates = weekDates(isoWeek)
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-7">
      {DAY_KEYS.map((dayKey, i) => (
        <DayColumn
          key={dayKey}
          dayKey={dayKey}
          date={dates[i]}
          entries={week[dayKey] ?? []}
          blocks={week.blocks?.[dayKey] ?? []}
          events={calendar[dayKey] ?? []}
          readOnly={readOnly}
          openIds={openIds}
          poolById={poolById}
          onToggle={onToggle}
          onRemoveTask={onRemoveTask}
          onRemoveBlock={onRemoveBlock}
        />
      ))}
    </div>
  )
}

function DayColumn({
  dayKey,
  date,
  entries,
  blocks,
  events,
  readOnly,
  openIds,
  poolById,
  onToggle,
  onRemoveTask,
  onRemoveBlock,
}: {
  dayKey: DayKey
  date: Date
  entries: Assignment[]
  blocks: DeepWorkBlock[]
  events: DayEvent[]
  readOnly: boolean
  openIds: Set<string>
  poolById: Map<string, PoolTask>
  onToggle: (taskId: string) => void
  onRemoveTask: (taskId: string) => void
  onRemoveBlock: (day: DayKey, blockId: string) => void
}) {
  const { setNodeRef, isOver } = useDroppable({ id: dayKey, disabled: readOnly })
  const today = isToday(date)
  const sorted = [...entries].sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
  const empty = sorted.length === 0 && blocks.length === 0 && events.length === 0

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex min-h-[200px] flex-col rounded-lg border bg-bg-panel transition-colors",
        today ? "border-accent" : "border-border",
        isOver && "border-accent-dim bg-bg-panel-hover ring-1 ring-accent-dim",
      )}
    >
      <div
        className={cn(
          "sticky top-0 z-10 flex items-baseline justify-between gap-2 rounded-t-lg border-b border-border bg-bg-panel px-3 py-2",
          today && "bg-accent-soft/20",
        )}
      >
        <span className="text-sm font-medium text-text">
          {dayLabel(dayKey)}{" "}
          <span className="font-mono text-xs text-text-secondary tabular-nums">
            ({dayDateLabel(date)})
          </span>
        </span>
        {today && <span className="text-[10px] uppercase tracking-wider text-accent">today</span>}
      </div>

      <div className="flex flex-1 flex-col gap-1.5 p-2">
        {/* Layer 1 — calendar events (non-draggable, visually distinct). */}
        {events.map((e, i) => (
          <EventChip key={`ev-${i}`} event={e} />
        ))}

        {/* Layer 2 — deep-work blocks. */}
        {blocks.map((b) => (
          <BlockCard
            key={b.id}
            block={b}
            readOnly={readOnly}
            onRemove={() => onRemoveBlock(dayKey, b.id)}
          />
        ))}

        {/* Layer 3 — tasks. */}
        {sorted.map((entry) => (
          <DayTaskCard
            key={entry.task_id}
            entry={entry}
            done={!openIds.has(entry.task_id)}
            readOnly={readOnly}
            fallbackText={poolById.get(entry.task_id)?.text}
            onToggle={() => onToggle(entry.task_id)}
            onRemove={() => onRemoveTask(entry.task_id)}
          />
        ))}

        {empty && (
          <p className="px-1 py-2 text-xs text-text-label">
            {readOnly ? "—" : "drop tasks or a block"}
          </p>
        )}
      </div>
    </div>
  )
}

/** Calendar event overlay — flat, muted, with a leading clock, never draggable. */
function EventChip({ event }: { event: DayEvent }) {
  return (
    <div className="flex items-center gap-1.5 rounded-md border border-dashed border-border bg-bg/60 px-1.5 py-1">
      <CalendarClock className="h-3 w-3 shrink-0 text-text-label" />
      {event.start && (
        <span className="shrink-0 font-mono text-[10px] text-text-label tabular-nums">
          {event.start}
        </span>
      )}
      <span className="min-w-0 truncate text-[11px] text-text-secondary">{event.title}</span>
    </div>
  )
}

function BlockCard({
  block,
  readOnly,
  onRemove,
}: {
  block: DeepWorkBlock
  readOnly: boolean
  onRemove: () => void
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: blockDragId(block.id),
    disabled: readOnly,
  })
  return (
    <div
      ref={setNodeRef}
      style={{ borderColor: block.color, backgroundColor: `${block.color}1f` }}
      className={cn(
        "group flex items-center gap-1.5 rounded-md border-l-4 border border-border px-1.5 py-1.5",
        isDragging && "opacity-40",
      )}
    >
      {!readOnly && (
        <button
          type="button"
          className="shrink-0 cursor-grab text-text-disabled hover:text-text-secondary active:cursor-grabbing"
          {...attributes}
          {...listeners}
          aria-label="drag block"
        >
          <GripVertical className="h-3.5 w-3.5" />
        </button>
      )}
      <div className="min-w-0 flex-1">
        <span className="block truncate text-xs font-medium text-text">
          {block.project}
          {block.title ? <span className="font-normal text-text-secondary"> — {block.title}</span> : null}
        </span>
        <span className="font-mono text-[10px] text-text-label">
          deep-work · {formatDuration(block.duration_min)}
        </span>
      </div>
      {!readOnly && (
        <button
          type="button"
          onClick={onRemove}
          aria-label="remove block"
          className="shrink-0 text-text-disabled opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
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
          {text ? <InlineMd text={stripTags(text)} /> : "(removed from source)"}
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
