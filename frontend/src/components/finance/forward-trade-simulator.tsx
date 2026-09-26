import { useMemo, useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Toggle } from "@/components/ui/toggle"
import { EmptyState } from "@/components/ui/empty-state"
import { useStockUniverse } from "@/hooks/usePortfolioHub"
import { useForwardWhatIf, type ForwardWhatIfResponse } from "@/hooks/useFinance"
import { useBenchmark } from "@/hooks/useBenchmark"
import { cn, formatCurrency, formatNumber, formatPercent } from "@/lib/utils"

const BENCHMARK_LABELS: Record<string, string> = {
  MSCI_WORLD: "MSCI World",
  SPY: "S&P 500",
  DAX: "DAX 40",
  STOXX_600: "STOXX 600",
}

/** ApiError carries the raw response body; FastAPI errors are {"detail": "..."}. */
function errorDetail(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e)
  try {
    const d = JSON.parse(raw)?.detail
    if (typeof d === "string") return d
    if (Array.isArray(d)) return d.map((x) => x?.msg ?? String(x)).join("; ")
  } catch {
    /* not JSON — show as is */
  }
  return raw
}

const pp = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${formatNumber(Math.abs(v) * 100, 1)}pp`

/**
 * Forward Trade Simulator (Chunk 7, D5) — "what if I buy/sell €X of TICKER?" Shows the
 * bucket allocation and drift vs the 49/21/24/6 targets before and after, the Sharpe /
 * Sortino / vol impact (forward Sharpe uses CAPM against the shared benchmark), which
 * bucket a buy lands in, and warnings for bucket-band, hard-trigger, per-position and
 * concentration breaches. EUR-based — distinct from the Watchlist tab's %-weight simulator.
 */
export function ForwardTradeSimulator() {
  const [benchmark] = useBenchmark()
  const universe = useStockUniverse()
  const sim = useForwardWhatIf()
  const [ticker, setTicker] = useState("")
  const [action, setAction] = useState<"buy" | "sell">("buy")
  const [amount, setAmount] = useState("5000")
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ForwardWhatIfResponse | null>(null)

  const options = useMemo(() => {
    const q = ticker.trim().toLowerCase()
    const all = [
      ...(universe.data?.held ?? []).map((e) => ({ ...e, group: "held" })),
      ...(universe.data?.watchlist ?? []).map((e) => ({ ...e, group: "watchlist" })),
    ]
    return all.filter((e) => !q || e.ticker.toLowerCase().includes(q) || e.name.toLowerCase().includes(q)).slice(0, 12)
  }, [universe.data, ticker])

  const amountNum = Number(amount)
  const canRun = ticker.trim() !== "" && amountNum > 0 && !sim.isPending

  function run() {
    setError(null)
    sim.mutate(
      { ticker: ticker.trim().toUpperCase(), action, eur_amount: amountNum },
      {
        onSuccess: (r) => setResult(r),
        onError: (e) => {
          setResult(null)
          setError(errorDetail(e))
        },
      },
    )
  }

  return (
    <Panel
      title="forward trade simulator"
      statusDotColor="accent"
      meta={`in € · sharpe vs ${BENCHMARK_LABELS[benchmark] ?? benchmark}`}
    >
      <div className="flex flex-wrap items-end gap-3">
        <label className="relative text-xs text-text-label">
          ticker
          <Input
            mono
            className="mt-1 w-48"
            value={ticker}
            placeholder="e.g. ADBE"
            onChange={(e) => {
              setTicker(e.target.value)
              setOpen(true)
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => setOpen(false)}
            onKeyDown={(e) => e.key === "Enter" && canRun && run()}
            aria-label="ticker"
            autoComplete="off"
          />
          {open && options.length > 0 && (
            <ul
              role="listbox"
              className="absolute z-20 mt-1 max-h-60 w-72 overflow-y-auto rounded-sm border border-border bg-bg-panel py-1 shadow-lg"
            >
              {options.map((o) => (
                <li key={o.ticker}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={o.ticker === ticker}
                    // mousedown, not click: the input's blur would close the list before a click lands
                    onMouseDown={(e) => {
                      e.preventDefault()
                      setTicker(o.ticker)
                      setOpen(false)
                    }}
                    className="flex w-full items-center gap-2 px-2 py-1 text-left text-sm hover:bg-bg-panel-hover"
                  >
                    <span className="font-mono text-text">{o.ticker}</span>
                    <span className="min-w-0 flex-1 truncate text-text-secondary">{o.name !== o.ticker ? o.name : ""}</span>
                    <span className="text-[10px] uppercase tracking-wider text-text-label">{o.group}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </label>

        <div className="text-xs text-text-label">
          action
          <div className="mt-1">
            <Toggle
              value={action}
              options={[{ value: "buy", label: "buy" }, { value: "sell", label: "sell" }]}
              onChange={setAction}
            />
          </div>
        </div>

        <label className="text-xs text-text-label">
          amount (€)
          <Input
            mono type="number" min="0" step="100" className="mt-1 w-32" value={amount}
            onChange={(e) => setAmount(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && canRun && run()}
            aria-label="amount in euro"
          />
        </label>

        <Button onClick={run} disabled={!canRun}>
          {sim.isPending ? "simulating…" : "simulate"}
        </Button>
      </div>

      {error && (
        <p role="alert" className="mt-3 rounded-sm border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {!result && !error && (
        <EmptyState className="mt-3" message="pick a ticker and an amount to see the allocation, drift and risk impact" />
      )}
      {result && <Result r={result} />}
    </Panel>
  )
}

function Result({ r }: { r: ForwardWhatIfResponse }) {
  const buy = r.action === "buy"
  return (
    <div className="mt-4 space-y-4">
      <p className="text-sm text-text-secondary">
        <span className={cn("font-mono uppercase", buy ? "text-success" : "text-danger")}>{r.action}</span>{" "}
        <span className="font-mono text-text">{formatCurrency(r.eur_effective, "EUR", 0)}</span> of{" "}
        <span className="font-mono text-text">{r.ticker}</span> ≈{" "}
        <span className="font-mono">{formatNumber(r.units, 2)}</span> units @ {formatCurrency(r.price_eur)}
        {buy && (
          <>
            {" "}→ maps to <span className="text-text">{r.bucket.label}</span>
            <span className="ml-1.5 rounded-sm border border-border px-1 text-[10px] uppercase tracking-wider text-text-label">
              {r.bucket.source === "override" ? "custom" : r.bucket.source === "map" ? "auto" : "no bucket"}
            </span>
          </>
        )}
      </p>

      {r.warnings.length > 0 && (
        <ul className="space-y-1" aria-label="warnings">
          {r.warnings.map((w, i) => (
            <li key={i} className="flex gap-2 rounded-sm border border-warning/30 bg-warning/10 px-3 py-1.5 text-sm text-warning">
              <span aria-hidden>⚠</span>
              <span>{w}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-text-label">
                <th className="py-1.5 pr-2 font-normal">bucket</th>
                <th className="px-2 py-1.5 text-right font-normal">current</th>
                <th className="px-2 py-1.5 text-right font-normal">projected</th>
                <th className="px-2 py-1.5 text-right font-normal">Δ weight</th>
                <th className="px-2 py-1.5 text-right font-normal">target</th>
                <th className="px-2 py-1.5 text-right font-normal">drift now → after</th>
              </tr>
            </thead>
            <tbody className="font-mono tabular-nums">
              {r.bucket_table.map((b) => {
                const breached = r.bucket_band_breaches.some((x) => x.bucket === b.bucket)
                const touched = r.bucket.bucket === b.bucket || (r.bucket.bucket === "unassigned" && b.bucket === "single_stocks")
                return (
                  <tr key={b.bucket} className={cn("border-b border-border/40", touched && "bg-invest/10")}>
                    <td className="py-1.5 pr-2 font-sans text-text">{b.label}</td>
                    <td className="px-2 py-1.5 text-right text-text-secondary">{formatPercent(b.current_weight * 100, 1).replace(/^\+/, "")}</td>
                    <td className="px-2 py-1.5 text-right text-text">{formatPercent(b.projected_weight * 100, 1).replace(/^\+/, "")}</td>
                    <td className={cn("px-2 py-1.5 text-right", b.weight_delta === 0 ? "text-text-label" : b.weight_delta > 0 ? "text-success" : "text-danger")}>{pp(b.weight_delta)}</td>
                    <td className="px-2 py-1.5 text-right text-text-label">{formatNumber(b.target * 100, 0)} %</td>
                    <td className={cn("px-2 py-1.5 text-right", breached ? "text-warning" : "text-text-secondary")}>
                      {pp(b.current_drift)} → {pp(b.projected_drift)}
                      <span className="ml-1 text-xs text-text-label">({pp(b.drift_delta)})</span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="mt-1 text-xs text-text-label">
            portfolio {formatCurrency(r.portfolio_value.current, "EUR", 0)} → {formatCurrency(r.portfolio_value.projected, "EUR", 0)} · weights on cached native prices, like the Bucket Allocation panel
          </p>
        </div>

        <div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-text-label">
                <th className="py-1.5 pr-2 font-normal">risk</th>
                <th className="px-2 py-1.5 text-right font-normal">current</th>
                <th className="px-2 py-1.5 text-right font-normal">projected</th>
                <th className="px-2 py-1.5 text-right font-normal">Δ</th>
              </tr>
            </thead>
            <tbody className="font-mono tabular-nums">
              <MetricRow label="sharpe (capm)" hint="forward · follows the benchmark" m={r.metrics.sharpe_capm} />
              <MetricRow label="sharpe (realized)" m={r.metrics.sharpe_historical} />
              <MetricRow label="sortino" m={r.metrics.sortino} />
              <MetricRow label="volatility" m={r.metrics.vol} pct lowerIsBetter />
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function MetricRow({
  label,
  hint,
  m,
  pct = false,
  lowerIsBetter = false,
}: {
  label: string
  hint?: string
  m: { current: number | null; projected: number | null; delta: number | null }
  pct?: boolean
  lowerIsBetter?: boolean
}) {
  const fmt = (v: number | null) => (v == null ? "—" : pct ? `${formatNumber(v * 100, 1)} %` : formatNumber(v, 2))
  const good = m.delta == null || m.delta === 0 ? null : lowerIsBetter ? m.delta < 0 : m.delta > 0
  return (
    <tr className="border-b border-border/40">
      <td className="py-1.5 pr-2 font-sans text-text" title={hint}>{label}</td>
      <td className="px-2 py-1.5 text-right text-text-secondary">{fmt(m.current)}</td>
      <td className="px-2 py-1.5 text-right text-text">{fmt(m.projected)}</td>
      <td className={cn("px-2 py-1.5 text-right", good == null ? "text-text-label" : good ? "text-success" : "text-danger")}>
        {m.delta == null ? "—" : `${m.delta > 0 ? "+" : m.delta < 0 ? "−" : ""}${pct ? `${formatNumber(Math.abs(m.delta) * 100, 1)}pp` : formatNumber(Math.abs(m.delta), 2)}`}
      </td>
    </tr>
  )
}
