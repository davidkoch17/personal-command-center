import { useState } from "react"
import { FileText, Square, X } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import type { StatusColor } from "@/components/ui/status-dot"
import { useManualTasks, type ManualTask } from "@/hooks/useHome"
import { openInOs } from "@/lib/open-in-os"

const SHOW_MAX = 5
const DISMISS_KEY = "cc.manual-tasks.dismissed"

/**
 * "Awaiting your input" — bottom-of-Home checklist (Manual_Tasks_Card_Spec.md)
 * of vault files that need David's manual fill before their dashboard features
 * fully work. Auto-resolves server-side: a correctly filled file drops off the
 * list on the next fetch — no marking-done.
 *
 * The whole section hides when all_clear. Rows can be dismissed for the
 * session (sessionStorage — that's the spec's "re-appears next session if
 * still pending" behavior; localStorage would never expire).
 */
export function ManualTasksCard() {
  const { data, isLoading } = useManualTasks()
  const [dismissed, setDismissed] = useState<string[]>(() => {
    try {
      const raw = sessionStorage.getItem(DISMISS_KEY)
      const parsed = raw ? (JSON.parse(raw) as unknown) : []
      return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : []
    } catch {
      return []
    }
  })

  if (isLoading) return <Skeleton className="h-20" />
  // Auto-hide when nothing is waiting on David.
  if (!data || data.all_clear) return null

  const visible = data.tasks.filter((t) => !dismissed.includes(t.id))
  if (visible.length === 0) return null

  function dismiss(id: string) {
    const next = [...dismissed, id]
    setDismissed(next)
    try {
      sessionStorage.setItem(DISMISS_KEY, JSON.stringify(next))
    } catch {
      /* best effort */
    }
  }

  const shown = visible.slice(0, SHOW_MAX)
  const overflow = visible.length - shown.length

  return (
    <Panel
      title="awaiting your input"
      meta={`${visible.length} pending`}
      statusDotColor={sectionDot(visible)}
    >
      <div className="space-y-3">
        {shown.map((t) => (
          <TaskRow key={t.id} task={t} onDismiss={() => dismiss(t.id)} />
        ))}
        {overflow > 0 && (
          <p className="font-mono text-xs text-text-label">+ {overflow} more pending</p>
        )}
      </div>
    </Panel>
  )
}

/** 🔴 any high · 🟡 any medium · 🟢 all low (or none). */
function sectionDot(tasks: ManualTask[]): StatusColor {
  if (tasks.some((t) => t.priority === "high")) return "danger"
  if (tasks.some((t) => t.priority === "medium")) return "warning"
  return "success"
}

function TaskRow({ task, onDismiss }: { task: ManualTask; onDismiss: () => void }) {
  return (
    <div className="rounded-sm border border-border bg-bg-panel/40 px-3 py-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Square className="h-3.5 w-3.5 shrink-0 text-text-label" />
          <span className="truncate text-sm font-medium text-text">{task.title}</span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="font-mono text-xs text-text-secondary tabular-nums">
            ~{task.estimated_time}
          </span>
          <button
            type="button"
            onClick={onDismiss}
            aria-label="dismiss for this session"
            title="dismiss for this session"
            className="text-text-label hover:text-text"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <p className="mt-1 pl-5 text-xs text-text-secondary">{task.what}</p>
      <div className="mt-1 flex flex-wrap items-center gap-2 pl-5">
        <button
          type="button"
          onClick={() => void openInOs(task.file_path)}
          className="flex min-w-0 items-center gap-1 font-mono text-xs text-accent hover:underline"
          title={`${task.file_path} · ${task.section}`}
        >
          <FileText className="h-3 w-3 shrink-0" />
          <span className="truncate">{task.file_path}</span>
        </button>
        <Button variant="ghost" size="sm" onClick={() => void openInOs(task.file_path)}>
          open file
        </Button>
      </div>
      <p className="mt-1 pl-5 text-xs text-text-label">{task.why}</p>
    </div>
  )
}
