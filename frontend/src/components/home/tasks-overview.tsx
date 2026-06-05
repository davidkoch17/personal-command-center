import { useNavigate } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusDot } from "@/components/ui/status-dot"
import { InlineMd } from "@/components/ui/inline-markdown"
import { useTasksSummary } from "@/hooks/useHome"

/**
 * GROUND §3b — compact tasks overview: open + high-priority counts and the top
 * 3 items from "This week". Click-through to the Tasks page.
 */
export function TasksOverview() {
  const { data, isLoading } = useTasksSummary()
  const navigate = useNavigate()

  return (
    <Panel
      title="tasks"
      meta={data ? `${data.open} open · ${data.high_priority} high-priority` : undefined}
      statusDotColor={data && data.high_priority > 0 ? "warning" : "accent"}
    >
      {isLoading ? (
        <Skeleton className="h-20" />
      ) : !data || data.top.length === 0 ? (
        <p className="text-sm text-text-label">nothing queued this week</p>
      ) : (
        <div className="space-y-1.5">
          {data.top.map((t, i) => (
            <button
              key={i}
              type="button"
              onClick={() => navigate("/tasks")}
              className="flex w-full items-start gap-2 rounded-sm px-1 py-0.5 text-left hover:bg-bg-panel-hover"
            >
              <StatusDot color="muted" />
              <span className="line-clamp-1 text-sm text-text-secondary">
                <InlineMd text={t.text} />
              </span>
            </button>
          ))}
        </div>
      )}
    </Panel>
  )
}
