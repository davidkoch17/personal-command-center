import { useState } from "react"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { InlineMd } from "@/components/ui/inline-markdown"
import type { WeekStats } from "@/lib/planner"

/**
 * Collapsible week-progress bar. Closed: a thin accent-filled bar + "N/M done
 * (X%)". Expanded: every completed task this week with its day + source.
 */
export function WeekStatsDropdown({ stats }: { stats?: WeekStats }) {
  const [open, setOpen] = useState(false)
  const total = stats?.total ?? 0
  const done = stats?.done ?? 0
  const pct = stats?.percentage ?? 0

  return (
    <div className="rounded-lg border border-border bg-bg-panel">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 px-3 py-2.5 text-left"
      >
        <ChevronRight
          className={cn(
            "h-4 w-4 shrink-0 text-text-secondary transition-transform",
            open && "rotate-90",
          )}
        />
        {/* Progress bar */}
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-bg">
          <div
            className="h-full rounded-full bg-accent transition-[width]"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="shrink-0 font-mono text-xs text-text-secondary tabular-nums">
          {done}/{total} done ({pct}%)
        </span>
      </button>

      {open && (
        <div className="border-t border-border px-3 py-2.5">
          {!stats || stats.done_tasks.length === 0 ? (
            <p className="text-sm text-text-label">nothing completed yet this week.</p>
          ) : (
            <ul className="space-y-1">
              {stats.done_tasks.map((t) => (
                <li key={`${t.day}-${t.id}`} className="flex items-baseline gap-2 text-sm">
                  <span className="w-20 shrink-0 font-mono text-[10px] uppercase tracking-wider text-text-label">
                    {t.day}
                  </span>
                  <span className="text-text-secondary line-through">
                    <InlineMd text={t.text} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
