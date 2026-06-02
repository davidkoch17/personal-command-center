import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { NumberDisplay } from "@/components/ui/number-display"
import {
  useWatchlistMetrics,
  useFinanceHoldings,
  useSimulateAdd,
  type WatchlistMetric,
  type SimulateAddResponse,
} from "@/hooks/useFinance"

function num(v: number | null | undefined, d = 2): string {
  return v == null ? "—" : v.toFixed(d)
}
function pct(v: number | null | undefined, d = 1): string {
  return v == null ? "—" : `${(v * 100).toFixed(d)}%`
}

/** Watchlist comparison tab — watchlist names scored on the same metrics as held
 *  positions, plus an "add to portfolio" simulation. */
export function WatchlistComparisonTab() {
  const metrics = useWatchlistMetrics()
  const holdings = useFinanceHoldings()
  const heldTickers = new Set((holdings.data?.holdings ?? []).map((h) => h.ticker.toUpperCase()))

  const rows = (metrics.data?.metrics ?? []).filter((m): m is WatchlistMetric & { sharpe: number } => !m.error)
  const errored = (metrics.data?.metrics ?? []).filter((m) => m.error)

  // Portfolio averages for the "vs my portfolio" reference line.
  const held = holdings.data?.holdings ?? []
  const avg = (key: "sharpe" | "volatility" | "beta") => {
    const vals = held.map((h) => h[key]).filter((v): v is number => typeof v === "number")
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null
  }

  return (
    <div className="space-y-4">
      <Panel
        title="watchlist — same metrics as holdings"
        meta={metrics.data ? `${rows.length} scored · beta vs ${metrics.data.beta_benchmark}` : undefined}
        statusDotColor="accent"
      >
        {metrics.isLoading ? (
          <Skeleton className="h-64" />
        ) : rows.length === 0 ? (
          <p className="text-sm text-text-label">no watchlist names with enough price history</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-text-label">
                  <th className="py-1.5 pr-2 font-normal">ticker</th>
                  <th className="py-1.5 px-2 text-right font-normal">sharpe</th>
                  <th className="py-1.5 px-2 text-right font-normal">vol</th>
                  <th className="py-1.5 px-2 text-right font-normal">beta</th>
                  <th className="py-1.5 px-2 text-right font-normal">max dd</th>
                  <th className="py-1.5 px-2 text-right font-normal">3m</th>
                  <th className="py-1.5 px-2 text-right font-normal">12m</th>
                  <th className="py-1.5 pl-2 font-normal">held?</th>
                </tr>
              </thead>
              <tbody className="font-mono tabular-nums">
                {/* Portfolio reference row. */}
                <tr className="border-b border-border/60 bg-bg-panel-hover/40 text-text-secondary">
                  <td className="py-1.5 pr-2 font-sans italic">my portfolio (avg)</td>
                  <td className="py-1.5 px-2 text-right">{num(avg("sharpe"))}</td>
                  <td className="py-1.5 px-2 text-right">{pct(avg("volatility"))}</td>
                  <td className="py-1.5 px-2 text-right">{num(avg("beta"))}</td>
                  <td className="py-1.5 px-2 text-right">—</td>
                  <td className="py-1.5 px-2 text-right">—</td>
                  <td className="py-1.5 px-2 text-right">—</td>
                  <td className="py-1.5 pl-2">—</td>
                </tr>
                {rows.map((m) => (
                  <tr key={m.ticker} className="border-b border-border/40">
                    <td className="py-1.5 pr-2 text-accent">{m.ticker}</td>
                    <td className="py-1.5 px-2 text-right text-text">{num(m.sharpe)}</td>
                    <td className="py-1.5 px-2 text-right text-text">{pct(m.volatility)}</td>
                    <td className="py-1.5 px-2 text-right text-text">{num(m.beta)}</td>
                    <td className="py-1.5 px-2 text-right text-danger">{pct(m.max_drawdown)}</td>
                    <td className={`py-1.5 px-2 text-right ${(m.momentum_3m ?? 0) >= 0 ? "text-success" : "text-danger"}`}>
                      {pct(m.momentum_3m)}
                    </td>
                    <td className={`py-1.5 px-2 text-right ${(m.momentum_12m ?? 0) >= 0 ? "text-success" : "text-danger"}`}>
                      {pct(m.momentum_12m)}
                    </td>
                    <td className="py-1.5 pl-2 font-sans text-xs">
                      {heldTickers.has(m.ticker.toUpperCase()) ? (
                        <span className="text-success">held</span>
                      ) : (
                        <span className="text-text-label">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {errored.length > 0 && (
              <p className="mt-2 text-xs text-text-label">
                {errored.length} name(s) skipped (no/short price history): {errored.map((e) => e.ticker).join(", ")}
              </p>
            )}
          </div>
        )}
      </Panel>

      <SimulateAddPanel />
    </div>
  )
}

function SimulateAddPanel() {
  const sim = useSimulateAdd()
  const [ticker, setTicker] = useState("")
  const [weight, setWeight] = useState("5")
  const [result, setResult] = useState<SimulateAddResponse | null>(null)

  function run() {
    const t = ticker.trim().toUpperCase()
    const w = (parseFloat(weight) || 0) / 100
    if (!t || w <= 0) return
    sim.mutate({ ticker: t, weight: w }, { onSuccess: (r) => setResult(r) })
  }

  return (
    <Panel title="simulate add to portfolio" meta="modeled marginal effect" statusDotColor="accent">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-32">
          <div className="label mb-1">ticker</div>
          <Input mono value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="NKE" />
        </div>
        <div className="w-28">
          <div className="label mb-1">weight %</div>
          <Input mono type="number" value={weight} onChange={(e) => setWeight(e.target.value)} />
        </div>
        <Button disabled={!ticker.trim() || sim.isPending} onClick={run}>
          simulate
        </Button>
      </div>

      <div className="mt-4">
        {sim.isPending ? (
          <Skeleton className="h-16" />
        ) : result == null ? (
          <p className="text-sm text-text-label">pick a watchlist name to model its effect on Sharpe / vol / beta</p>
        ) : !result.available ? (
          <p className="text-sm text-text-label">{result.reason ?? "not enough data to model"}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-8">
            <Delta label="Δ sharpe" v={result.modeled_metrics?.delta_sharpe} ratio />
            <Delta label="Δ vol" v={result.modeled_metrics?.delta_volatility} pct invert />
            <Delta label="Δ beta" v={result.modeled_metrics?.delta_beta} ratio invert />
            <div>
              <div className="label mb-0.5">corr to portfolio</div>
              <span className="font-mono text-xl text-text tabular-nums">
                {num(result.modeled_metrics?.correlation_to_portfolio)}
              </span>
            </div>
          </div>
        )}
      </div>
    </Panel>
  )
}

function Delta({
  label,
  v,
  pct: isPct,
  ratio,
  invert,
}: {
  label: string
  v: number | null | undefined
  pct?: boolean
  ratio?: boolean
  invert?: boolean
}) {
  // "good" = improvement: higher sharpe is good; lower vol/beta is good (invert).
  const good = v == null ? false : invert ? v < 0 : v > 0
  const color = v == null || v === 0 ? "text-text-label" : good ? "text-success" : "text-danger"
  return (
    <div>
      <div className="label mb-0.5">{label}</div>
      {v == null ? (
        <span className="font-mono text-xl text-text-label">—</span>
      ) : isPct ? (
        <NumberDisplay value={v * 100} format="percent" signed decimals={2} className={`text-xl ${color}`} />
      ) : (
        <span className={`font-mono text-xl tabular-nums ${color}`}>
          {v > 0 ? "+" : ""}
          {v.toFixed(ratio ? 3 : 2)}
        </span>
      )}
    </div>
  )
}
