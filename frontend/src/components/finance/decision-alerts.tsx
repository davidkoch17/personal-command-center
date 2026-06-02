import { useNavigate } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { useDecisionSummary } from "@/hooks/useFinance"
import { formatCurrency } from "@/lib/utils"

/**
 * Home "decision alerts" block — active rebalance recommendations, concentration
 * alerts, and tax-loss harvest opportunities as headline counts. Clicking any
 * card deep-links into the Portfolio workspace Decisions tab.
 */
export function DecisionAlerts() {
  const { data, isLoading } = useDecisionSummary()
  const navigate = useNavigate()

  const open = () => navigate("/workspace/portfolio?tab=decisions")

  const totalActive = data
    ? data.rebalance_count + data.concentration_count + data.harvest_count
    : 0

  return (
    <Panel
      title="decision alerts"
      meta={data ? `${totalActive} active` : undefined}
      statusDotColor={
        data && (data.concentration_high > 0 || data.rebalance_high > 0)
          ? "warning"
          : totalActive > 0
            ? "accent"
            : "muted"
      }
    >
      {isLoading ? (
        <Skeleton className="h-16" />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <AlertCard
            label="rebalance"
            count={data?.rebalance_count ?? 0}
            sub={data?.rebalance_high ? `${data.rebalance_high} high priority` : "within tolerance"}
            tone={data?.rebalance_high ? "warning" : "muted"}
            onClick={open}
          />
          <AlertCard
            label="concentration"
            count={data?.concentration_count ?? 0}
            sub={data?.concentration_high ? `${data.concentration_high} over cap` : "all within caps"}
            tone={data?.concentration_high ? "danger" : "muted"}
            onClick={open}
          />
          <AlertCard
            label="tax-loss harvest"
            count={data?.harvest_count ?? 0}
            sub={
              data && data.harvest_count > 0
                ? `~${formatCurrency(data.harvest_savings)} savings`
                : "no losses"
            }
            tone={data && data.harvest_count > 0 ? "warning" : "muted"}
            onClick={open}
          />
        </div>
      )}
    </Panel>
  )
}

function AlertCard({
  label,
  count,
  sub,
  tone,
  onClick,
}: {
  label: string
  count: number
  sub: string
  tone: "danger" | "warning" | "muted"
  onClick: () => void
}) {
  const countColor = count === 0 ? "text-text-label" : tone === "danger" ? "text-danger" : tone === "warning" ? "text-warning" : "text-text"
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-sm border border-border bg-bg-panel px-3 py-2 text-left transition-colors hover:border-accent-dim"
    >
      <div className="label mb-0.5">{label}</div>
      <div className="flex items-baseline gap-2">
        <span className={`font-mono text-2xl font-medium tabular-nums ${countColor}`}>{count}</span>
        <span className="text-xs text-text-secondary">{sub}</span>
      </div>
    </button>
  )
}
