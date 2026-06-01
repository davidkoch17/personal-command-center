import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { NumberDisplay } from "@/components/ui/number-display"
import { MetricPanel } from "@/components/finance/metric-panel"
import { HoldingsTable } from "@/components/finance/holdings-table"
import { usePortfolioSnapshot, usePortfolioPerformance } from "@/hooks/useFinance"

export function Portfolio() {
  const snap = usePortfolioSnapshot()
  const ytd = usePortfolioPerformance("ytd")

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">portfolio</h1>
        <Button asChild variant="secondary" size="sm">
          <a href="/workspace/portfolio" target="_blank" rel="noopener noreferrer">
            open workspace ↗
          </a>
        </Button>
      </div>

      {/* Top metrics */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricPanel
          label="total value"
          value={
            snap.isLoading ? (
              <Skeleton className="h-7 w-28" />
            ) : (
              <NumberDisplay value={snap.data?.total_value} format="currency" emphasized />
            )
          }
          caption={`${snap.data?.position_count ?? 0} positions`}
        />
        <MetricPanel
          label="p&l today"
          dotColor="muted"
          value={<span className="text-text-label">—</span>}
          caption="no intraday source"
        />
        <MetricPanel
          label="p&l ytd"
          dotColor={
            (ytd.data?.change_pct ?? 0) >= 0 ? "success" : "danger"
          }
          value={
            ytd.isLoading ? (
              <Skeleton className="h-7 w-20" />
            ) : (
              <NumberDisplay value={ytd.data?.change_pct} format="percent" signed />
            )
          }
        />
        <MetricPanel
          label="cash deployable"
          dotColor="success"
          value={
            snap.isLoading ? (
              <Skeleton className="h-7 w-28" />
            ) : (
              <NumberDisplay value={snap.data?.cash_deployable} format="currency" />
            )
          }
        />
      </div>

      {/* Holdings table */}
      <Panel title="holdings" meta={`${snap.data?.holdings.length ?? 0} positions`} statusDotColor="accent">
        {snap.isLoading ? (
          <Skeleton className="h-40" />
        ) : snap.isError ? (
          <p className="text-text-secondary">could not load holdings. backend on :8000?</p>
        ) : (
          <HoldingsTable holdings={snap.data?.holdings ?? []} />
        )}
      </Panel>

      {/* Signals + recent activity (no aggregate endpoints yet) */}
      <div className="grid gap-4 md:grid-cols-2">
        <Panel title="watchlist signals" statusDotColor="muted">
          <p className="text-sm text-text-label">
            brief signals surface per-name in the watchlist workspace (no aggregate endpoint yet)
          </p>
        </Panel>
        <Panel title="recent activity" statusDotColor="muted">
          <p className="text-sm text-text-label">
            portfolio-action log endpoint pending (backend phase)
          </p>
        </Panel>
      </div>
    </div>
  )
}
