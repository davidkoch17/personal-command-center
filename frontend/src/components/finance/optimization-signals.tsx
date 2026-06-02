import { Link } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useOptSignals } from "@/hooks/useFinance"

function ratio(v: number | null | undefined): string {
  return v == null ? "—" : v.toFixed(2)
}

/**
 * Home "optimization signals" block — current Sharpe vs the max-Sharpe achievable
 * (the improvement gap) and current diversification vs the min-variance target,
 * with a jump-off to the full optimization workspace.
 */
export function OptimizationSignals() {
  const { data, isLoading } = useOptSignals()

  return (
    <Panel
      title="optimization signals"
      meta={data?.available && data.sharpe_gap != null ? `+${ratio(data.sharpe_gap)} sharpe available` : undefined}
      statusDotColor={data?.available && (data.sharpe_gap ?? 0) > 0.1 ? "warning" : "accent"}
    >
      {isLoading ? (
        <Skeleton className="h-16" />
      ) : !data?.available ? (
        <p className="text-sm text-text-label">{data?.reason ?? "not available"}</p>
      ) : (
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-wrap gap-6">
            <Stat label="current sharpe" value={ratio(data.current_sharpe)} />
            <Stat label="max sharpe" value={ratio(data.max_sharpe)} accent />
            <Stat label="effective bets" value={ratio(data.current_effective_bets)} />
            <Stat
              label="min-var target"
              value={ratio(data.min_variance_effective_bets)}
              sub="diversification"
            />
          </div>
          <Button asChild variant="secondary" size="sm">
            <Link to="/workspace/portfolio">view full optimization →</Link>
          </Button>
        </div>
      )}
    </Panel>
  )
}

function Stat({
  label,
  value,
  sub,
  accent,
}: {
  label: string
  value: string
  sub?: string
  accent?: boolean
}) {
  return (
    <div>
      <div className="label mb-0.5">{label}</div>
      <span className={`font-mono text-xl font-medium tabular-nums ${accent ? "text-accent" : "text-text"}`}>
        {value}
      </span>
      {sub && <div className="text-[10px] text-text-label">{sub}</div>}
    </div>
  )
}
