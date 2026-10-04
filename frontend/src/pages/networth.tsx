import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { NetworthDonut } from "@/components/networth/networth-donut"
import { NetworthTrendChart } from "@/components/networth/networth-trend"
import { MilestoneTracker } from "@/components/networth/milestone-tracker"
import { AccountsHierarchy } from "@/components/networth/accounts-hierarchy"
import { useNetworthSnapshot, type NetworthPeriod } from "@/hooks/useNetworth"

/**
 * Net Worth pillar (Chunk 9.7) — 4th sidebar pillar, a full page (not a tab)
 * giving the holistic bottom-up view: bank + brokerage cash plus every
 * holding by bucket. Independent of the Portfolio pillar's live-ledger
 * decomposition and of Excel's authoritative net worth — see
 * modules/finance/networth.py's module docstring for why all three can
 * legitimately disagree.
 */
export function Networth() {
  const [period, setPeriod] = useState<NetworthPeriod>("3M")
  const snap = useNetworthSnapshot(period)

  if (snap.isLoading) {
    return (
      <div className="space-y-5">
        <h1 className="text-2xl font-semibold tracking-tight">net worth</h1>
        <Skeleton className="h-80 w-full" />
        <Skeleton className="h-56 w-full" />
      </div>
    )
  }

  if (snap.isError || !snap.data) {
    return (
      <div className="space-y-5">
        <h1 className="text-2xl font-semibold tracking-tight">net worth</h1>
        <EmptyState message="couldn't load the net worth snapshot — try reloading" />
      </div>
    )
  }

  const { breakdown, delta_this_month, trend, milestone, accounts } = snap.data

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-tight">net worth</h1>

      <Panel title="breakdown" statusDotColor="invest">
        <NetworthDonut breakdown={breakdown} deltaThisMonth={delta_this_month} />
      </Panel>

      <Panel title="trend">
        <NetworthTrendChart trend={trend} period={period} onPeriodChange={setPeriod} />
      </Panel>

      <Panel title="milestone">
        <MilestoneTracker milestone={milestone} />
      </Panel>

      <Panel title="accounts">
        <AccountsHierarchy accounts={accounts} />
      </Panel>
    </div>
  )
}
