import { EmptyState } from "@/components/ui/empty-state"
import { Target } from "lucide-react"
import { formatCurrency } from "@/lib/utils"
import type { NetworthMilestone } from "@/hooks/useNetworth"

/** Section 3 — progress bar toward the current goal in config/networth_targets.yaml,
 * plus a linear-trend projection (or why one isn't shown). */
export function MilestoneTracker({ milestone }: { milestone: NetworthMilestone }) {
  if (!milestone.available) {
    return (
      <EmptyState
        icon={Target}
        message={milestone.reason ?? "no goal configured — add one in config/networth_targets.yaml"}
      />
    )
  }

  const pct = milestone.pct ?? 0

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium text-text">{milestone.label}</span>
        <span className="font-mono text-sm tabular-nums text-text-secondary">
          {formatCurrency(milestone.current ?? 0)} / {formatCurrency(milestone.target ?? 0)} ({pct.toFixed(0)}%)
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-bg-panel-hover">
        <div
          className="h-full rounded-full bg-invest transition-[width]"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <p className="text-xs text-text-secondary">
        {milestone.status === "reached" && "Goal reached — add a new one in config/networth_targets.yaml."}
        {milestone.status === "insufficient_history" && "Need at least 90 days of history for a projection."}
        {milestone.status === "paused" &&
          "Flat/negative 3-month trend — projection paused."}
        {milestone.status === "on_track" &&
          milestone.monthly_rate != null &&
          milestone.months_to_goal != null &&
          milestone.projected_date && (
            <>
              At your 3-month trend (+{formatCurrency(milestone.monthly_rate)}/mo avg), you'll reach this in{" "}
              {milestone.months_to_goal} months (approx {milestone.projected_date}).
            </>
          )}
      </p>
    </div>
  )
}
