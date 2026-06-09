import { useMemo } from "react"
import { Zap, Plus } from "lucide-react"
import { cn } from "@/lib/utils"
import { InlineMd } from "@/components/ui/inline-markdown"
import { BUSY_TAGS, stripTags, tagsOf, type PoolTask } from "@/lib/planner"

interface BusyTaskBarProps {
  tasks: PoolTask[]
  assignedTaskIds: Set<string>
  readOnly: boolean
  /** Grab a quick task into today's column ("start it now"). */
  onStart: (taskId: string) => void
}

/**
 * Bottom full-width bar of quick-grab tasks (<1h) for an open hour — filtered to
 * the #quick / #busy tag convention. Click a chip to drop it onto today; this is
 * an at-a-glance grab list, not the full pool.
 */
export function BusyTaskBar({ tasks, assignedTaskIds, readOnly, onStart }: BusyTaskBarProps) {
  const quick = useMemo(
    () =>
      tasks.filter(
        (t) => !assignedTaskIds.has(t.id) && tagsOf(t).some((tag) => BUSY_TAGS.includes(tag)),
      ),
    [tasks, assignedTaskIds],
  )

  return (
    <div className="rounded-lg border border-border bg-bg-panel">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Zap className="h-3.5 w-3.5 shrink-0 text-accent" />
        <span className="label">busy-task bar</span>
        <span className="font-mono text-[10px] text-text-label">&lt;1h · quick grabs</span>
        <span className="ml-auto font-mono text-xs text-text-secondary">{quick.length}</span>
      </div>
      {quick.length === 0 ? (
        <p className="px-3 py-2.5 text-sm text-text-label">
          no quick tasks — tag tasks{" "}
          <code className="font-mono text-[11px] text-text-secondary">#quick</code> or{" "}
          <code className="font-mono text-[11px] text-text-secondary">#busy</code> to surface them here.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2 p-2.5">
          {quick.map((t) => (
            <button
              key={t.id}
              type="button"
              disabled={readOnly}
              onClick={() => onStart(t.id)}
              title={readOnly ? undefined : "drop onto today"}
              className={cn(
                "group flex max-w-[16rem] items-center gap-1.5 rounded-md border border-border bg-bg px-2 py-1.5 text-left transition-colors",
                readOnly ? "cursor-default" : "hover:border-accent-dim hover:bg-bg-panel-hover",
              )}
            >
              {!readOnly && (
                <Plus className="h-3 w-3 shrink-0 text-text-disabled group-hover:text-accent" />
              )}
              <span className="min-w-0 truncate text-xs text-text">
                <InlineMd text={stripTags(t.text)} />
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
