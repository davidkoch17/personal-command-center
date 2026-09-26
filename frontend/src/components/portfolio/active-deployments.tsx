import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { Button } from "@/components/ui/button"
import { DeploymentPlanModal, NewPlanModal, targetLabel } from "@/components/portfolio/deployment-plan-modal"
import { useDeploymentPlans, type DeploymentPlan } from "@/hooks/usePortfolioHub"
import { cn, formatCurrency } from "@/lib/utils"

/** "Next: 30% in 12 days" / "due today" / "overdue by 3 days". */
function nextText(p: DeploymentPlan): string | null {
  const n = p.progress.next_tranche
  if (!n) return null
  const d = n.days_until
  const when = d > 1 ? `in ${d} days` : d === 1 ? "tomorrow" : d === 0 ? "today" : `overdue by ${-d} day${d === -1 ? "" : "s"}`
  return `Next: ${n.pct}% ${when}`
}

/**
 * Active deployments (Chunk 6, C6) — the 50/30/20 lump-sum tranche tracker on the
 * Portfolio tab: one card per in-progress plan (progress bar, next-tranche
 * countdown, ●●○ tranche dots); click a card for its schedule and to mark tranches
 * executed, or "+ New plan" to plan a deployment.
 */
export function ActiveDeployments() {
  const { data, isLoading } = useDeploymentPlans("in_progress")
  const [openId, setOpenId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const plans = data?.plans ?? []
  const count = data?.summary.active_count ?? plans.length

  return (
    <Panel
      title="active deployments"
      statusDotColor="invest"
      meta={
        <span className="flex items-center gap-2">
          <span className="rounded-sm border border-invest/30 bg-invest/10 px-1.5 text-[10px] text-invest" aria-label="active plans">
            {count}
          </span>
          <Button size="sm" variant="secondary" onClick={() => setCreating(true)}>
            + New plan
          </Button>
        </span>
      }
    >
      {isLoading ? (
        <Skeleton className="h-24" />
      ) : plans.length === 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <EmptyState message="no active deployment plans" />
          <Button size="sm" onClick={() => setCreating(true)}>
            plan a deployment
          </Button>
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {plans.map((p) => (
            <PlanCard key={p.id} plan={p} onOpen={() => setOpenId(p.id)} />
          ))}
        </div>
      )}

      <DeploymentPlanModal planId={openId} onClose={() => setOpenId(null)} />
      <NewPlanModal open={creating} onOpenChange={setCreating} />
    </Panel>
  )
}

function PlanCard({ plan, onOpen }: { plan: DeploymentPlan; onOpen: () => void }) {
  const pr = plan.progress
  const next = nextText(plan)
  const overdue = (pr.next_tranche?.days_until ?? 0) < 0
  return (
    <button
      type="button"
      onClick={onOpen}
      className="rounded-sm border border-border bg-bg p-3 text-left transition-colors hover:border-invest/50 hover:bg-bg-panel-hover"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-text">{plan.name}</div>
          <div className="text-xs text-text-secondary">
            <span className="font-mono">{formatCurrency(plan.total_eur, "EUR", 0)}</span> → {targetLabel(plan)}
          </div>
        </div>
        <span className="font-mono text-sm tabular-nums text-invest">{pr.deployed_pct.toFixed(0)}%</span>
      </div>

      <div
        className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-border"
        role="progressbar"
        aria-valuenow={pr.deployed_pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${plan.name} deployed`}
      >
        <div className="h-full rounded-full bg-invest transition-all" style={{ width: `${Math.min(100, pr.deployed_pct)}%` }} />
      </div>

      <div className="mt-2 flex items-center justify-between gap-2 text-xs">
        <span className={cn(overdue ? "text-warning" : "text-text-secondary")}>{next ?? "no pending tranches"}</span>
        <span className="flex items-center gap-1 font-mono text-sm tracking-widest" aria-label={`${pr.executed_count} of ${pr.tranche_count} tranches executed`}>
          {plan.schedule.map((t, i) => (
            <span key={i} className={t.executed ? "text-invest" : "text-text-label"} title={`${t.pct}% · ${t.target_date}${t.executed ? " · executed" : ""}`}>
              {t.executed ? "●" : "○"}
            </span>
          ))}
        </span>
      </div>
    </button>
  )
}
