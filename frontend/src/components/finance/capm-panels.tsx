import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { TimeframePills } from "@/components/ui/timeframe-pills"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { SecurityMarketLineChart } from "@/components/charts/finance-analytics-charts"
import { useCapmDecomposition, useSml, type CapmDecompRow } from "@/hooks/useFinance"
import { cn, formatNumber, formatPercent } from "@/lib/utils"

const BENCHMARK_LABELS: Record<string, string> = {
  MSCI_WORLD: "MSCI World",
  SPY: "S&P 500",
  DAX: "DAX 40",
  STOXX_600: "STOXX 600",
}

const PERIODS = [
  { key: "1m", label: "1M" },
  { key: "3m", label: "3M" },
  { key: "6m", label: "6M" },
  { key: "ytd", label: "YTD" },
  { key: "1y", label: "1Y" },
  { key: "3y", label: "3Y" },
  { key: "all", label: "ALL" },
] as const
type Period = (typeof PERIODS)[number]["key"]

// A value that rounds to zero prints as "0,0 %" rather than "−0,0 %" (e.g. the benchmark's own alpha).
const pct = (v: number | null | undefined, d = 1) => {
  if (v == null) return "—"
  const rounded = Number((v * 100).toFixed(d))
  return rounded === 0 ? formatNumber(0, d) + " %" : formatPercent(v * 100, d)
}

/**
 * Security Market Line (Chunk 6, D3). Each holding sits at (beta, actual annualized
 * return); the line is the CAPM-expected return ``rf + beta * (E[rm] - rf)`` — the
 * same regression, window and 4% risk-free rate as the Optimization tab's expected
 * returns. Above the line = positive alpha. Follows the shared benchmark selection.
 */
export function SecurityMarketLinePanel({ benchmark }: { benchmark: string }) {
  const { data, isLoading } = useSml(benchmark)
  const label = BENCHMARK_LABELS[benchmark] ?? benchmark

  return (
    <Panel
      title="security market line"
      statusDotColor="accent"
      meta={data?.line ? `capm vs ${label} · rf ${formatNumber(data.risk_free_rate * 100, 0)}%` : undefined}
    >
      {isLoading ? (
        <Skeleton className="h-80" />
      ) : !data?.available || !data.line ? (
        <EmptyState message={data?.reason ?? "no benchmark price history for the security market line"} />
      ) : (
        <>
          <SecurityMarketLineChart line={data.line} points={data.points} portfolio={data.portfolio} market={data.market} />
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-label">
            <span><span className="text-success">●</span> above the line (alpha &gt; 0)</span>
            <span><span className="text-danger">●</span> below the line</span>
            <span><span className="text-invest">◆</span> portfolio</span>
            <span>line: E[r] = rf + β × (E[rm] − rf), E[rm] = {pct(data.market?.expected_return)} / yr</span>
          </div>
          {data.points.length === 0 && (
            <p className="mt-1 text-xs text-text-label">{data.reason === "no holdings" ? "no holdings — the line is drawn without points" : data.reason}</p>
          )}
        </>
      )}
    </Panel>
  )
}

function Signed({ v }: { v: number | null | undefined }) {
  return (
    <span className={cn(v == null ? "text-text-label" : v >= 0 ? "text-success" : "text-danger")}>{pct(v)}</span>
  )
}

/**
 * CAPM return decomposition (Chunk 6, D4). Over the chosen period each holding's
 * realized return splits into market (β × the benchmark's return), alpha (the
 * regression intercept accrued over the period) and idiosyncratic (the remainder),
 * which sum exactly to the actual return. Portfolio row = current-weight roll-up.
 */
export function CapmDecompositionPanel({ benchmark }: { benchmark: string }) {
  const [period, setPeriod] = useState<Period>("1y")
  const { data, isLoading } = useCapmDecomposition(benchmark, period)
  const label = BENCHMARK_LABELS[benchmark] ?? benchmark

  return (
    <Panel
      title="capm return decomposition"
      statusDotColor="accent"
      meta={data?.market_return != null ? `${label} ${pct(data.market_return)} over ${data.days}d` : `vs ${label}`}
    >
      <TimeframePills options={PERIODS} value={period} onChange={setPeriod} className="mb-3" />
      {isLoading && !data ? (
        <Skeleton className="h-40" />
      ) : !data?.available || data.rows.length === 0 ? (
        <EmptyState message={data?.reason ?? "no holdings to decompose"} />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ticker</TableHead>
                <TableHead className="text-right">β</TableHead>
                <TableHead className="text-right">actual return</TableHead>
                <TableHead className="text-right">market (β × rm)</TableHead>
                <TableHead className="text-right">alpha</TableHead>
                <TableHead className="text-right">idiosyncratic</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.rows.map((r) => (
                <DecompRow key={r.ticker} r={r} />
              ))}
              {data.portfolio && <DecompRow r={data.portfolio} total />}
            </TableBody>
          </Table>
          <p className="mt-2 text-xs text-text-label">
            market + alpha + idiosyncratic = actual. β and alpha come from a 5-year regression on {label}; idiosyncratic is
            whatever the market model leaves unexplained (it also absorbs compounding). Portfolio uses current weights.
          </p>
        </>
      )}
    </Panel>
  )
}

function DecompRow({ r, total = false }: { r: CapmDecompRow; total?: boolean }) {
  return (
    <TableRow className={cn(total && "border-t-2 border-border bg-bg-panel-hover font-semibold")}>
      <TableCell className="font-mono">{total ? "portfolio" : r.ticker}</TableCell>
      <TableCell className="text-right font-mono tabular-nums">{r.beta != null ? formatNumber(r.beta, 2) : "—"}</TableCell>
      <TableCell className="text-right font-mono tabular-nums"><Signed v={r.actual_return} /></TableCell>
      <TableCell className="text-right font-mono tabular-nums"><Signed v={r.market} /></TableCell>
      <TableCell className="text-right font-mono tabular-nums"><Signed v={r.alpha} /></TableCell>
      <TableCell className="text-right font-mono tabular-nums"><Signed v={r.idiosyncratic} /></TableCell>
    </TableRow>
  )
}
