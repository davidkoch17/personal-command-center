import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { TimeframePills } from "@/components/ui/timeframe-pills"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { BenchmarkComparisonChart, CorrelationHeatmap } from "@/components/charts/finance-analytics-charts"
import { BENCHMARK_COLORS } from "@/components/charts/theme"
import { useBenchmarkComparison, type BenchmarkKey4 } from "@/hooks/usePortfolioHub"
import { cn, formatNumber, formatPercent } from "@/lib/utils"

const TIMEFRAMES = [
  { key: "1m", label: "1M" },
  { key: "3m", label: "3M" },
  { key: "6m", label: "6M" },
  { key: "ytd", label: "YTD" },
  { key: "1y", label: "1Y" },
  { key: "3y", label: "3Y" },
  { key: "all", label: "ALL" },
] as const
type Period = (typeof TIMEFRAMES)[number]["key"]

// The all-window chart would ship ~2,400 rows x 4 series to Recharts; thin to a
// readable density (always keeping the last point).
const MAX_CHART_ROWS = 600

const dash = "—"

function Swatch({ k }: { k: string }) {
  return <span className="mr-2 inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: BENCHMARK_COLORS[k] }} />
}

/**
 * Benchmarks tab (Chunk 5) — MSCI World vs S&P 500 vs DAX 40 vs STOXX 600 over one
 * shared timeframe: return / vol / Sharpe / correlation-to-MSCI, all four indexed
 * to 100 on one chart, and the full 4x4 correlation matrix. One backend call
 * (/benchmarks/compare) feeds all three sections so they always agree. Sharpe uses
 * the same 4% risk-free rate as the Risk and Optimization tabs.
 */
export function BenchmarksTab() {
  const [period, setPeriod] = useState<Period>("1y")
  const { data, isLoading } = useBenchmarkComparison(period)

  const available = data?.benchmarks.filter((b) => b.available) ?? []
  const rows = data?.series ?? []
  const step = Math.max(1, Math.ceil(rows.length / MAX_CHART_ROWS))
  const chartRows = rows.filter((_, i) => i % step === 0 || i === rows.length - 1)

  // The shared heatmap component keys its rows by ticker string; use display names.
  const corr = data?.correlation
  const heatmapRows = (corr?.labels ?? []).map((label, i) => ({
    ticker: label,
    ...Object.fromEntries((corr?.labels ?? []).map((l, j) => [l, corr?.matrix[i]?.[j] ?? 0])),
  }))

  return (
    <div className="space-y-5">
      {/* 1. Timeframe */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="label">timeframe</span>
        <TimeframePills options={TIMEFRAMES} value={period} onChange={setPeriod} />
        {data?.start && (
          <span className="font-mono text-xs text-text-label">
            {data.start} → {data.end}
          </span>
        )}
      </div>

      {/* 2. Metrics: one row per benchmark */}
      <Panel title="benchmark comparison" statusDotColor="invest" meta={data ? `sharpe @ ${formatNumber(data.risk_free_rate * 100, 0)}% rf` : undefined}>
        {isLoading && !data ? (
          <Skeleton className="h-40" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>benchmark</TableHead>
                <TableHead className="text-right">return</TableHead>
                <TableHead className="text-right">volatility (ann.)</TableHead>
                <TableHead className="text-right">sharpe</TableHead>
                <TableHead className="text-right">correlation to msci world</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.benchmarks ?? []).map((b) => {
                const m = data!.metrics[b.key as BenchmarkKey4]
                const ret = m.return
                return (
                  <TableRow key={b.key} className={cn(b.key === "MSCI_WORLD" && "bg-invest/10")}>
                    <TableCell>
                      <div className="flex items-center">
                        <Swatch k={b.key} />
                        <span className={cn(b.key === "MSCI_WORLD" && "font-semibold text-invest")}>{b.name}</span>
                        <span className="ml-2 font-mono text-xs text-text-label">{b.ticker}</span>
                        {b.key === "MSCI_WORLD" && (
                          <span className="ml-2 rounded-sm border border-invest/30 bg-invest/10 px-1 text-[10px] uppercase tracking-wider text-invest">
                            primary
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className={cn("text-right font-mono tabular-nums", ret == null ? "text-text-label" : ret >= 0 ? "text-success" : "text-danger")}>
                      {ret != null ? formatPercent(ret * 100, 1).replace("%", " %") : dash}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {m.vol != null ? `${formatNumber(m.vol * 100, 1)} %` : dash}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {m.sharpe != null ? formatNumber(m.sharpe, 2) : dash}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums" title={b.key === "MSCI_WORLD" ? "the reference itself" : undefined}>
                      {b.key === "MSCI_WORLD" || m.correlation_to_msci == null ? dash : formatNumber(m.correlation_to_msci, 2)}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </Panel>

      {/* 3. Indexed chart */}
      <Panel title="indexed to 100" statusDotColor="invest" meta={data?.start ? `since ${data.start}` : undefined}>
        {isLoading && !data ? (
          <Skeleton className="h-72" />
        ) : chartRows.length > 1 ? (
          <BenchmarkComparisonChart
            data={chartRows}
            series={available.map((b) => ({ key: b.key, name: b.name, color: BENCHMARK_COLORS[b.key] }))}
          />
        ) : (
          <EmptyState message="no benchmark price history available" />
        )}
      </Panel>

      {/* 4. Correlation matrix */}
      <Panel title="correlation matrix" statusDotColor="invest" meta={`daily returns · ${period}`}>
        {isLoading && !data ? (
          <Skeleton className="h-52" />
        ) : heatmapRows.length > 0 ? (
          <CorrelationHeatmap tickers={corr!.labels} matrix={heatmapRows} scale="invest" size="lg" />
        ) : (
          <EmptyState message="not enough overlapping history for a correlation matrix" />
        )}
      </Panel>
    </div>
  )
}
