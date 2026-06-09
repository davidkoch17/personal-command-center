import { useMemo, useState } from "react"
import { useDroppable, useDraggable } from "@dnd-kit/core"
import { GripVertical, Search, CornerDownLeft } from "lucide-react"
import { cn } from "@/lib/utils"
import { InlineMd } from "@/components/ui/inline-markdown"
import { TASK_TAGS, stripTags, tagsOf, type PoolTask, type TaskTag } from "@/lib/planner"

interface PlanTaskPoolProps {
  tasks: PoolTask[]
  assignedTaskIds: Set<string>
  readOnly: boolean
  onToggle: (taskId: string) => void
}

const TAG_STYLE: Record<TaskTag, string> = {
  quick: "bg-accent-soft text-accent",
  "deep-work": "bg-warning/15 text-warning",
  busy: "bg-text-disabled/25 text-text-secondary",
}

/**
 * The Plan task pool — unassigned + carry-forward open tasks, doubling as the
 * all-tasks view (it replaces the standalone Tasks page). Filterable by free
 * text and by the quick / deep-work / busy tag convention. Drag a task onto the
 * grid to schedule it; drop it back here to unassign.
 */
export function PlanTaskPool({ tasks, assignedTaskIds, readOnly, onToggle }: PlanTaskPoolProps) {
  const { setNodeRef, isOver } = useDroppable({ id: "pool", disabled: readOnly })
  const [query, setQuery] = useState("")
  const [tagFilter, setTagFilter] = useState<TaskTag | null>(null)

  // Server already filters assigned tasks out, but a freshly-dragged task may
  // still be present until the pool query refetches — hide those optimistically.
  const visible = useMemo(
    () => tasks.filter((t) => !assignedTaskIds.has(t.id)),
    [tasks, assignedTaskIds],
  )

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return visible.filter((t) => {
      if (tagFilter && !tagsOf(t).includes(tagFilter)) return false
      if (!q) return true
      return t.text.toLowerCase().includes(q) || t.source_label.toLowerCase().includes(q)
    })
  }, [visible, query, tagFilter])

  const carry = filtered.filter((t) => t.is_carry_forward)
  const rest = filtered.filter((t) => !t.is_carry_forward)

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex max-h-[calc(100vh-260px)] flex-col rounded-lg border bg-bg-panel transition-colors",
        isOver ? "border-accent-dim ring-1 ring-accent-dim" : "border-border",
      )}
    >
      <div className="border-b border-border px-3 py-2.5">
        <div className="mb-2 flex items-center justify-between">
          <span className="label">all open tasks</span>
          <span className="font-mono text-xs text-text-secondary">{visible.length} open</span>
        </div>
        <div className="mb-2 flex items-center gap-2 rounded-md border border-border bg-bg px-2 py-1.5">
          <Search className="h-3.5 w-3.5 shrink-0 text-text-label" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="filter tasks..."
            className="w-full bg-transparent text-sm text-text placeholder:text-text-label focus:outline-none"
          />
        </div>
        {/* Tag filter chips. */}
        <div className="flex flex-wrap gap-1">
          {TASK_TAGS.map((tag) => (
            <button
              key={tag}
              type="button"
              onClick={() => setTagFilter((cur) => (cur === tag ? null : tag))}
              className={cn(
                "rounded-sm px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider transition-colors",
                tagFilter === tag
                  ? TAG_STYLE[tag]
                  : "bg-bg text-text-label hover:text-text-secondary",
              )}
            >
              #{tag}
            </button>
          ))}
          {tagFilter && (
            <button
              type="button"
              onClick={() => setTagFilter(null)}
              className="rounded-sm px-1.5 py-0.5 text-[10px] text-text-label hover:text-text"
            >
              clear
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 space-y-1.5 overflow-y-auto p-2">
        {filtered.length === 0 ? (
          <p className="px-1 py-3 text-sm text-text-label">
            {visible.length === 0 ? "pool is empty — all tasks assigned" : "no matches"}
          </p>
        ) : (
          <>
            {carry.length > 0 && (
              <>
                <div className="px-1 pb-0.5 pt-1 text-[10px] uppercase tracking-wider text-text-label">
                  from last week
                </div>
                {carry.map((t) => (
                  <PoolTaskCard key={t.id} task={t} readOnly={readOnly} onToggle={() => onToggle(t.id)} />
                ))}
                {rest.length > 0 && <div className="my-1 border-t border-border" />}
              </>
            )}
            {rest.map((t) => (
              <PoolTaskCard key={t.id} task={t} readOnly={readOnly} onToggle={() => onToggle(t.id)} />
            ))}
          </>
        )}
      </div>
    </div>
  )
}

function PoolTaskCard({
  task,
  readOnly,
  onToggle,
}: {
  task: PoolTask
  readOnly: boolean
  onToggle: () => void
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: task.id,
    disabled: readOnly,
  })
  const tags = tagsOf(task)

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
        aria-label="mark done"
        className="mt-1 h-3 w-3 shrink-0 rounded-full border border-text-label transition-colors hover:border-text-secondary disabled:cursor-not-allowed"
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-start gap-1.5">
          <span className="block text-xs leading-snug text-text">
            <InlineMd text={stripTags(task.text)} />
          </span>
          {task.is_carry_forward && (
            <span
              title="carried over from last week"
              className="inline-flex shrink-0 items-center gap-0.5 rounded-sm bg-warning/15 px-1 text-[9px] font-medium text-warning"
            >
              <CornerDownLeft className="h-2.5 w-2.5" /> last week
            </span>
          )}
          {tags.map((tag) => (
            <span
              key={tag}
              className={cn(
                "shrink-0 rounded-sm px-1 text-[9px] font-medium uppercase tracking-wider",
                TAG_STYLE[tag],
              )}
            >
              {tag}
            </span>
          ))}
        </div>
        <span className="mt-0.5 block truncate font-mono text-[10px] text-text-label">
          {task.source_label}
        </span>
      </div>
    </div>
  )
}
