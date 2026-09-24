import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Panel } from "@/components/ui/panel"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { EfficientFrontierScatter } from "@/components/charts/finance-analytics-charts"
import { api } from "@/lib/api"
import {
  useOptFrontier,
  useOptRiskParity,
  useBlackLitterman,
  useFinanceHoldings,
  useDistanceFromFrontier,
  type OptPortfolio,
} from "@/hooks/useFinance"
import { useBenchmark } from "@/hooks/useBenchmark"
import type { ConstrainedFrontierResult } from "@/hooks/useOptimizationConstrained"
import { ConstraintsModal } from "@/components/portfolio/constraints-modal"
import { cn } from "@/lib/utils"

type Weights = Record<string, number>

function pct(v: number | null | undefined, d = 1): string {
  return v == null ? "—" : `${(v * 100).toFixed(d)}%`
}

/** Optimization tab: efficient frontier, optimal-portfolio comparison, BL. */
export function OptimizationTab() {
  return (
    <Tabs defaultValue="frontier">
      <TabsList>
        <TabsTrigger value="frontier">efficient frontier</TabsTrigger>
        <TabsTrigger value="optimal">optimal portfolios</TabsTrigger>
        <TabsTrigger value="bl">black-litterman</TabsTrigger>
      </TabsList>
      <TabsContent value="frontier">
        <FrontierSubtab />
      </TabsContent>
      <TabsContent value="optimal">
        <OptimalSubtab />
      </TabsContent>
      <TabsContent value="bl">
        <BlackLittermanSubtab />
      </TabsContent>
    </Tabs>
  )
}

const BENCHMARK_LABELS: Record<string, string> = {
  MSCI_WORLD: "MSCI World",
  SPY: "S&P 500",
  DAX: "DAX 40",
  STOXX_600: "STOXX 600",
}

function toPoint(p: OptPortfolio | null | undefined): { risk: number; return: number } | null {
  return p?.performance ? { risk: p.performance.volatility, return: p.performance.expected_return } : null
}

function FrontierSubtab() {
  const { data, isLoading } = useOptFrontier(50)
  const holdings = useFinanceHoldings()
  const [benchmark] = useBenchmark()
  const distance = useDistanceFromFrontier(benchmark)
  const [modalOpen, setModalOpen] = useState(false)
  const [constrained, setConstrained] = useState<ConstrainedFrontierResult | null>(null)

  const overlay =
    constrained && constrained.feasible
      ? {
          points: constrained.points.map((p) => ({ risk: p.risk, return: p.return })),
          tangency: toPoint(constrained.tangency),
          minVariance: toPoint(constrained.mvp),
        }
      : null

  return (
    <div className="space-y-4">
      <Panel
        title="efficient frontier"
        meta={data ? `${data.points.length} points` : undefined}
        statusDotColor="accent"
      >
        {isLoading ? (
          <Skeleton className="h-80" />
        ) : !data || data.points.length === 0 ? (
          <p className="text-sm text-text-label">not enough data to build a frontier</p>
        ) : (
          <>
            <div className="mb-2 flex justify-end">
              <Button size="sm" variant="secondary" onClick={() => setModalOpen(true)}>
                {constrained ? "edit constraints" : "add my constraints"}
              </Button>
            </div>
            <EfficientFrontierScatter
              frontier={data.points.map((p) => ({ risk: p.risk, return: p.return }))}
              current={data.current ? { risk: data.current.risk, return: data.current.return } : null}
              maxSharpe={toPoint(data.max_sharpe)}
              minVariance={toPoint(data.min_variance)}
              riskFreeRate={data.risk_free_rate}
              constrained={overlay}
            />
            <p className="mt-2 text-xs text-text-label">
              ✦ max sharpe · ◆ min variance · ✕ your current portfolio · line = frontier · cyan = capital market line
              {overlay && " · dashed = unconstrained, solid = constrained"}
            </p>
            {constrained && !constrained.feasible && (
              <p className="mt-1 text-xs text-danger">{constrained.reason}</p>
            )}
          </>
        )}
      </Panel>

      <Panel title="distance from frontier" meta={`vs ${BENCHMARK_LABELS[benchmark] ?? benchmark}`} statusDotColor="muted">
        {distance.isLoading ? (
          <Skeleton className="h-12" />
        ) : !distance.data?.available ? (
          <p className="text-sm text-text-label">add positions to see distance from frontier</p>
        ) : (
          <DistanceCallout d={distance.data} />
        )}
      </Panel>

      {data && holdings.data && (
        <ConstraintsModal
          open={modalOpen}
          onOpenChange={setModalOpen}
          currentVol={data.current?.risk ?? null}
          unconstrainedTangency={data.max_sharpe}
          onPreview={setConstrained}
        />
      )}
    </div>
  )
}

function DistanceCallout({ d }: { d: NonNullable<ReturnType<typeof useDistanceFromFrontier>["data"]> }) {
  const gap = d.delta_bps
  return (
    <div>
      <p className="font-mono text-sm text-text">
        your: {d.portfolio_sharpe?.toFixed(2) ?? "—"} · tangency: {d.tangency_sharpe?.toFixed(2) ?? "—"} · gap:{" "}
        <span className={cn(gap != null && gap < 0 ? "text-danger" : "text-success")}>
          {gap != null ? `${gap > 0 ? "+" : ""}${Math.round(gap)} bps` : "—"}
        </span>
      </p>
      <p className="mt-1 text-xs text-text-label">
        your vol {pct(d.portfolio_vol)} · tangency vol {pct(d.tangency_vol)} · tangency uses CAPM expected returns
        against the selected benchmark, so it can differ from the ✦ on the chart (historical mean returns)
      </p>
    </div>
  )
}

function OptimalSubtab() {
  const [maxPos, setMaxPos] = useState("")
  const [minPos, setMinPos] = useState("")
  const holdings = useFinanceHoldings()
  const riskParity = useOptRiskParity()

  const qs = new URLSearchParams()
  if (maxPos) qs.set("max_position", maxPos)
  if (minPos) qs.set("min_position", minPos)
  const suffix = qs.toString() ? `?${qs.toString()}` : ""

  const maxSharpe = useQuery({
    queryKey: ["finance", "max-sharpe", maxPos, minPos],
    queryFn: () => api.get<OptPortfolio & { tickers: string[] }>(`/api/finance/optimization/max-sharpe${suffix}`),
  })
  const minVar = useQuery({
    queryKey: ["finance", "min-variance", maxPos, minPos],
    queryFn: () => api.get<OptPortfolio & { tickers: string[] }>(`/api/finance/optimization/min-variance${suffix}`),
  })

  // Current market-value weights from holdings.
  const current: Weights = {}
  for (const h of holdings.data?.holdings ?? []) {
    if (h.weight != null) current[h.ticker] = h.weight
  }

  const strategies = [
    { key: "current", label: "current", weights: current, perf: null as OptPortfolio["performance"] },
    { key: "minvar", label: "min variance", weights: minVar.data?.weights ?? {}, perf: minVar.data?.performance ?? null },
    { key: "maxsharpe", label: "max sharpe", weights: maxSharpe.data?.weights ?? {}, perf: maxSharpe.data?.performance ?? null },
    { key: "riskparity", label: "risk parity", weights: riskParity.data?.weights ?? {}, perf: null },
  ]

  const tickers = Array.from(
    new Set(strategies.flatMap((s) => Object.keys(s.weights))),
  ).sort()

  const loading = maxSharpe.isLoading || minVar.isLoading || riskParity.isLoading

  return (
    <div className="space-y-4">
      <Panel title="constraints" meta="section 0 bucket discipline" statusDotColor="muted">
        <div className="grid grid-cols-2 gap-3 sm:max-w-md">
          <div>
            <div className="label mb-1">max position weight</div>
            <Input
              type="number"
              value={maxPos}
              onChange={(e) => setMaxPos(e.target.value)}
              placeholder="e.g. 0.25"
              mono
            />
          </div>
          <div>
            <div className="label mb-1">min position weight</div>
            <Input
              type="number"
              value={minPos}
              onChange={(e) => setMinPos(e.target.value)}
              placeholder="e.g. 0.0"
              mono
            />
          </div>
        </div>
        <p className="mt-2 text-xs text-text-label">
          applied to min-variance + max-sharpe (decimals, e.g. 0.25 = 25%). sector
          caps need richer metadata (later phase).
        </p>
      </Panel>

      <Panel title="optimal portfolios" meta="current vs optimized weights" statusDotColor="accent">
        {loading ? (
          <Skeleton className="h-48" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-text-label">
                  <th className="py-1.5 pr-2 font-normal">ticker</th>
                  {strategies.map((s) => (
                    <th key={s.key} className="py-1.5 px-2 text-right font-normal">{s.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="font-mono tabular-nums">
                {tickers.map((t) => (
                  <tr key={t} className="border-b border-border/40">
                    <td className="py-1.5 pr-2 font-sans text-text">{t}</td>
                    {strategies.map((s) => {
                      const w = s.weights[t] ?? 0
                      return (
                        <td key={s.key} className={cn("py-1.5 px-2 text-right", w > 0 ? "text-text" : "text-text-label")}>
                          {pct(w)}
                        </td>
                      )
                    })}
                  </tr>
                ))}
                {/* Performance footer rows. */}
                <PerfRow label="exp. return" strategies={strategies} field="expected_return" pctv />
                <PerfRow label="volatility" strategies={strategies} field="volatility" pctv />
                <PerfRow label="sharpe" strategies={strategies} field="sharpe" />
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  )
}

function PerfRow({
  label,
  strategies,
  field,
  pctv,
}: {
  label: string
  strategies: { key: string; perf: OptPortfolio["performance"] }[]
  field: "expected_return" | "volatility" | "sharpe"
  pctv?: boolean
}) {
  return (
    <tr className="border-t border-border text-text-secondary">
      <td className="py-1.5 pr-2 font-sans text-xs">{label}</td>
      {strategies.map((s) => {
        const v = s.perf?.[field]
        return (
          <td key={s.key} className="py-1.5 px-2 text-right text-xs">
            {v == null ? "—" : pctv ? pct(v) : v.toFixed(2)}
          </td>
        )
      })}
    </tr>
  )
}

function BlackLittermanSubtab() {
  const { data, isLoading } = useBlackLitterman()

  return (
    <div className="space-y-4">
      <Panel
        title="views from hypothesis tracker"
        meta={data ? `${data.views_used.length} views` : undefined}
        statusDotColor="accent"
      >
        {isLoading ? (
          <Skeleton className="h-32" />
        ) : !data || data.views_used.length === 0 ? (
          <p className="text-sm text-text-label">
            no parseable views in Hypothesis_Tracker.md — BL falls back to max-sharpe.
          </p>
        ) : (
          <ul className="space-y-2 text-sm">
            {data.views_used.map((v, i) => (
              <li key={i} className="flex items-start justify-between gap-3 border-b border-border/40 pb-2">
                <div className="min-w-0">
                  <span className="font-mono text-accent">{v.ticker}</span>
                  <span className="ml-2 text-text-secondary">{v.label}</span>
                </div>
                <div className="shrink-0 text-right font-mono text-xs">
                  <div className="text-text">
                    {pct(v.expected_return)}{" "}
                    {v.derived && <span className="text-text-label" title="derived from conviction">~</span>}
                  </div>
                  <div className="text-text-label">conv {(v.confidence * 5).toFixed(0)}/5</div>
                </div>
              </li>
            ))}
          </ul>
        )}
        {data?.views_used.some((v) => v.derived) && (
          <p className="mt-2 text-xs text-text-label">
            ~ expected return derived from conviction (tracker states no explicit target); edit
            the hypothesis or POST explicit views to override.
          </p>
        )}
      </Panel>

      {data && (
        <Panel title="BL-suggested weights" meta="posterior-optimized" statusDotColor="accent">
          {isLoading ? (
            <Skeleton className="h-40" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-text-label">
                    <th className="py-1.5 pr-2 font-normal">ticker</th>
                    <th className="py-1.5 px-2 text-right font-normal">BL weight</th>
                    <th className="py-1.5 px-2 text-right font-normal">equilibrium</th>
                    <th className="py-1.5 px-2 text-right font-normal">posterior</th>
                  </tr>
                </thead>
                <tbody className="font-mono tabular-nums">
                  {data.tickers.map((t) => (
                    <tr key={t} className="border-b border-border/40">
                      <td className="py-1.5 pr-2 font-sans text-text">{t}</td>
                      <td className="py-1.5 px-2 text-right text-text">{pct(data.weights[t] ?? 0)}</td>
                      <td className="py-1.5 px-2 text-right text-text-secondary">{pct(data.market_equilibrium?.[t])}</td>
                      <td className="py-1.5 px-2 text-right text-text-secondary">{pct(data.posterior_returns?.[t])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.performance && (
                <div className="mt-3 flex gap-6 text-xs text-text-secondary">
                  <span>exp. return {pct(data.performance.expected_return)}</span>
                  <span>vol {pct(data.performance.volatility)}</span>
                  <span>sharpe {data.performance.sharpe.toFixed(2)}</span>
                </div>
              )}
            </div>
          )}
        </Panel>
      )}
    </div>
  )
}
