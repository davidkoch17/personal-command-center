import type { ReactNode } from "react"

interface KanbanColumnProps {
  stage: string
  count: number
  children: ReactNode
}

/** A single kanban column: lowercase stage header + scrollable card stack. */
export function KanbanColumn({ stage, count, children }: KanbanColumnProps) {
  return (
    <div className="flex min-w-[220px] flex-1 flex-col rounded-lg border border-border bg-bg-panel/40">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <span className="label">{stage.toLowerCase()}</span>
        <span className="font-mono text-xs text-text-label">{count}</span>
      </div>
      <div className="flex max-h-[70vh] flex-col gap-2 overflow-y-auto p-2">
        {count === 0 ? (
          <p className="px-1 py-2 text-xs text-text-label">empty</p>
        ) : (
          children
        )}
      </div>
    </div>
  )
}
