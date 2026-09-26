import { useState } from "react"
import { Link } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { NumberDisplay } from "@/components/ui/number-display"
import { MetricPanel } from "@/components/finance/metric-panel"
import { DecisionAlerts } from "@/components/finance/decision-alerts"
import { ActiveDeployments } from "@/components/portfolio/active-deployments"
import { CategoryDonut } from "@/components/charts/finance-charts"
import { IndexedPerformanceChart } from "@/components/charts/finance-analytics-charts"
import { useDashboardSummary, useDashboardPerformance, type DashboardTopHolding } from "@/hooks/usePortfolioHub"
import { useBuckets, type BucketRow } from "@/hooks/useFinance"
import { useBenchmark } from "@/hooks/useBenchmark"
import { cn, formatCurrency } from "@/lib/utils"

const TIMEFRAMES = [
  { key: "1d", label: "1D" },
  { key: "1w", label: "1W" },
  { key: "1m", label: "1M" },
  { key: "ytd", label: "YTD" },
  { key: "1y", label: "1Y" },
  { key: "all", label: "ALL" },
] as const

const BUCKET_COLOR: Record<string, string> = {
  etf_foundation: "#2563EB",
  single_stocks: "#14B8A6",
  crypto: "#F59E0B",
  wild_cards: "#A855F7",
}

const DRIFT_STATUS_COLOR: Record<BucketRow["status"], "success" | "warning" | "danger"> = {
  ok: "success",
  warn: "warning",
  alert: "danger",
}

/**
 * Portfolio tab (Chunk 2) — David's main portfolio dashboard: KPI band,
 * timeframe-toggle performance chart (portfolio vs benchmark, indexed to 100),
 * allocation-vs-target donut, top-5 holdings, and the shared decision-alerts
 * strip. Reuses the Risk tab's shared benchmark selection (useBenchmark) so
 * the MSCI/S&P/DAX/STOXX overlay here always matches what's picked elsewhere
 * in the workspace.
 */
export function PortfolioTab() {
  const [benchmark] = useBenchmark()
  const [timeframe, setTimeframe] = useState<string>("1w")

  const summary = useDashboardSummary(benchmark)
  const perf = useDashboardPerformance(timeframe, benchmark)
  const buckets = useBuckets()

  const s = summary.data

  return (
    <div className="space-y-5">
      {/* 1. KPI band */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricPanel
          label="portfolio value"
          value={
            summary.isLoading ? (
              <Skeleton className="h-7 w-32" />
            ) : (
              <NumberDisplay value={s?.portfolio_value_eur ?? 0} format="currency" className="text-invest" emphasized animate />
            )
          }
          caption={
            s?.day_change_eur != null ? (
              <span className="flex items-center gap-1.5">
                <NumberDisplay value={s.day_change_eur} format="currency" signed />
                {s.day_change_pct != null && (
                  <NumberDisplay value={s.day_change_pct * 100} format="percent" signed decimals={2} />
                )}
                <span className="text-text-label">today</span>
              </span>
            ) : (
              "no positions yet"
            )
          }
          dotColor={s?.day_change_eur == null ? "muted" : s.day_change_eur >= 0 ? "success" : "danger"}
        />

        <MetricPanel
          label="ytd return"
          value={
            summary.isLoading ? (
              <Skeleton className="h-7 w-24" />
            ) : (
              <NumberDisplay value={s?.ytd_return_pct != null ? s.ytd_return_pct * 100 : null} format="percent" signed decimals={2} className="text-invest" />
            )
          }
          caption={
            s?.ytd_return_eur != null ? (
              <span className="flex flex-col gap-0.5">
                <span>
                  <NumberDisplay value={s.ytd_return_eur} format="currency" signed /> ytd
                </span>
                <span className="text-text-label">
                  {s.benchmark_name} ytd:{" "}
                  {s.benchmark_ytd_return_pct != null ? (
                    <NumberDisplay value={s.benchmark_ytd_return_pct * 100} format="percent" signed decimals={2} />
                  ) : (
                    "—"
                  )}
                </span>
              </span>
            ) : (
              "n/a"
            )
          }
          dotColor={s?.ytd_return_pct == null ? "muted" : s.ytd_return_pct >= 0 ? "success" : "danger"}
        />

        <MetricPanel
          label="sharpe (1y)"
          value={
            summary.isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              <span className="font-mono text-2xl font-medium tabular-nums text-invest">
                {s?.sharpe_1y != null ? s.sharpe_1y.toFixed(2) : "—"}
              </span>
            )
          }
          caption={
            s ? (
              <>
                {s.benchmark_name} sharpe:{" "}
                {s.benchmark_sharpe_1y != null ? s.benchmark_sharpe_1y.toFixed(2) : "—"}
              </>
            ) : (
              "n/a"
            )
          }
          dotColor="invest"
        />

        <MetricPanel
          label="drift status"
          value={
            summary.isLoading ? (
              <Skeleton className="h-7 w-20" />
            ) : s?.worst_drift_bucket ? (
              <span
                className={cn(
                  "font-mono text-xl font-medium tabular-nums",
                  DRIFT_STATUS_COLOR[s.worst_drift_bucket.status] === "success" && "text-success",
                  DRIFT_STATUS_COLOR[s.worst_drift_bucket.status] === "warning" && "text-warning",
                  DRIFT_STATUS_COLOR[s.worst_drift_bucket.status] === "danger" && "text-danger",
                )}
              >
                {(s.worst_drift_bucket.drift * 100).toFixed(1)}pp
              </span>
            ) : (
              <span className="font-mono text-xl text-text-label">—</span>
            )
          }
          caption={s?.worst_drift_bucket?.label ?? "no bucketed holdings"}
          dotColor={s?.worst_drift_bucket ? DRIFT_STATUS_COLOR[s.worst_drift_bucket.status] : "muted"}
        />
      </div>

      {/* 2 + 3. Timeframe toggle + performance chart */}
      <Panel
        title="performance"
        meta={perf.data?.available ? `vs ${perf.data.benchmark_name}` : undefined}
        statusDotColor="invest"
      >
        <div className="mb-3 flex flex-wrap gap-1.5">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf.key}
              type="button"
              onClick={() => setTimeframe(tf.key)}
              className={cn(
                "rounded-sm border px-3 py-1 font-mono text-xs transition-colors",
                timeframe === tf.key
                  ? "border-accent text-accent bg-bg-panel-hover"
                  : "border-border text-text-secondary hover:text-text",
              )}
            >
              {tf.label}
            </button>
          ))}
        </div>

        {perf.isLoading ? (
          <Skeleton className="h-64" />
        ) : !perf.data?.available ? (
          <EmptyState message="no data yet — add a trade in Holdings to start tracking" className="py-10" />
        ) : (
          <>
            <IndexedPerformanceChart data={perf.data.series} benchmarkName={perf.data.benchmark_name ?? "benchmark"} />
            <p className="mt-2 text-xs text-text-label">
              both series indexed to 100 at the start of the selected window.
            </p>
          </>
        )}
      </Panel>

      {/* 4. Allocation vs target */}
      <AllocationVsTarget buckets={buckets.data?.buckets ?? []} loading={buckets.isLoading} />

      {/* 4b. Active deployments — the 50/30/20 tranche tracker (Chunk 6). */}
      <ActiveDeployments />

      {/* 5. Top holdings */}
      <Panel
        title="top holdings"
        meta={s ? `${s.holdings_count} position${s.holdings_count === 1 ? "" : "s"}` : undefined}
        statusDotColor="accent"
      >
        {summary.isLoading ? (
          <Skeleton className="h-32" />
        ) : !s?.top_holdings.length ? (
          <EmptyState message="No positions yet — add one from Holdings" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-text-label">
                  <th className="py-1.5 pr-3 font-normal">position</th>
                  <th className="py-1.5 px-3 font-normal">bucket</th>
                  <th className="py-1.5 px-3 text-right font-normal">weight</th>
                  <th className="py-1.5 pl-3 text-right font-normal">today</th>
                </tr>
              </thead>
              <tbody>
                {s.top_holdings.map((h) => (
                  <TopHoldingRow key={h.ticker} holding={h} />
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-3 flex justify-end">
          <Link to="/portfolio?tab=holdings" className="font-mono text-xs text-accent hover:underline">
            view all →
          </Link>
        </div>
      </Panel>

      {/* 6. Decision alerts — same strip + click-through as Overview. */}
      <DecisionAlerts />
    </div>
  )
}

function TopHoldingRow({ holding }: { holding: DashboardTopHolding }) {
  return (
    <tr className="border-b border-border/50 last:border-0">
      <td className="py-2 pr-3 font-mono text-text">{holding.ticker}</td>
      <td className="py-2 px-3 text-xs text-text-secondary">
        {holding.bucket ? holding.bucket.replace(/_/g, " ") : "—"}
      </td>
      <td className="py-2 px-3 text-right">
        <span className="font-mono tabular-nums text-text-secondary">
          {holding.weight != null ? `${(holding.weight * 100).toFixed(1)}%` : "—"}
        </span>
      </td>
      <td className="py-2 pl-3 text-right">
        {holding.day_change_pct != null ? (
          <NumberDisplay value={holding.day_change_pct * 100} format="percent" signed decimals={2} />
        ) : (
          <span className="font-mono text-text-label">—</span>
        )}
      </td>
    </tr>
  )
}

function AllocationVsTarget({ buckets, loading }: { buckets: BucketRow[]; loading: boolean }) {
  const total = buckets.reduce((s, b) => s + b.value, 0)
  const donutData = buckets
    .filter((b) => b.value > 0)
    .map((b) => ({ name: b.label, value: b.value }))

  return (
    <Panel title="allocation vs target" statusDotColor="accent">
      {loading ? (
        <Skeleton className="h-48" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            {total > 0 ? (
              <CategoryDonut data={donutData} height={220} />
            ) : (
              <div className="flex h-[220px] items-center justify-center">
                <div className="h-28 w-28 rounded-full border-8 border-border" />
              </div>
            )}
          </div>
          <div className="flex flex-col justify-center gap-2.5">
            {buckets.map((b) => (
              <div key={b.bucket} className="flex items-center gap-2.5">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: BUCKET_COLOR[b.bucket] ?? "#64748B" }}
                />
                <span className="min-w-0 flex-1 truncate text-sm text-text-secondary">{b.label}</span>
                <span className="font-mono text-sm tabular-nums text-text">
                  {(b.current_weight * 100).toFixed(1)}%
                </span>
                <span className="font-mono text-xs text-text-label">/ {(b.target_weight * 100).toFixed(0)}%</span>
                <span
                  className={cn(
                    "font-mono text-xs tabular-nums",
                    DRIFT_STATUS_COLOR[b.status] === "success" && "text-success",
                    DRIFT_STATUS_COLOR[b.status] === "warning" && "text-warning",
                    DRIFT_STATUS_COLOR[b.status] === "danger" && "text-danger",
                  )}
                >
                  {b.drift > 0 ? "+" : ""}
                  {(b.drift * 100).toFixed(1)}pp
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      {total === 0 && (
        <p className="mt-3 text-xs text-text-label">
          no bucketed holdings yet — targets shown above are the Investment Philosophy §0 caps
          ({formatCurrency(0)} allocated so far).
        </p>
      )}
    </Panel>
  )
}
