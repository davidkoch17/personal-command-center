import { useEffect, useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { NumberDisplay } from "@/components/ui/number-display"
import {
  useDecisionRebalance,
  useDecisionHarvest,
  useDecisionAlerts,
  useSuggestSize,
  type RebalanceRec,
  type SizeResponse,
} from "@/hooks/useFinance"
import { formatCurrency } from "@/lib/utils"

const BUCKET_LABELS: Record<string, string> = {
  etf_foundation: "ETF Foundation",
  single_stocks: "Single Stocks",
  crypto: "Crypto",
  wild_cards: "Wild Cards",
}

function pct(v: number | null | undefined, d = 1): string {
  return v == null ? "—" : `${(v * 100).toFixed(d)}%`
}

function severityColor(s: string): "danger" | "warning" | "muted" {
  if (s === "high") return "danger"
  if (s === "medium") return "warning"
  return "muted"
}

/** Decisions tab — rebalance, tax-loss harvest, concentration alerts, sizing. */
export function DecisionsTab() {
  return (
    <div className="space-y-4">
      <RebalancePanel />
      <div className="grid gap-4 lg:grid-cols-2">
        <HarvestPanel />
        <ConcentrationPanel />
      </div>
      <SizingPanel />
    </div>
  )
}

function RebalancePanel() {
  const { data, isLoading } = useDecisionRebalance()
  const allocations = data?.allocations ?? {}
  const recs = data?.recommendations ?? []

  return (
    <Panel
      title="rebalance recommendations"
      meta={data ? `${recs.length} suggested · ±${pct(data.drift_tolerance, 0)} band` : undefined}
      statusDotColor={recs.some((r) => r.priority === "high") ? "warning" : "accent"}
    >
      {isLoading ? (
        <Skeleton className="h-48" />
      ) : (
        <div className="space-y-4">
          {/* Bucket vs target table. */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-text-label">
                  <th className="py-1.5 pr-2 font-normal">bucket</th>
                  <th className="py-1.5 px-2 text-right font-normal">current</th>
                  <th className="py-1.5 px-2 text-right font-normal">target</th>
                  <th className="py-1.5 px-2 text-right font-normal">drift</th>
                  <th className="py-1.5 px-2 text-right font-normal">value</th>
                </tr>
              </thead>
              <tbody className="font-mono tabular-nums">
                {Object.entries(allocations).map(([bucket, a]) => (
                  <tr key={bucket} className="border-b border-border/40">
                    <td className="py-1.5 pr-2 font-sans text-text">{BUCKET_LABELS[bucket] ?? bucket}</td>
                    <td className="py-1.5 px-2 text-right text-text">{pct(a.weight)}</td>
                    <td className="py-1.5 px-2 text-right text-text-secondary">{pct(a.target)}</td>
                    <td
                      className={`py-1.5 px-2 text-right ${
                        Math.abs(a.drift) > (data?.drift_tolerance ?? 0.04) ? "text-warning" : "text-text-label"
                      }`}
                    >
                      {a.drift > 0 ? "+" : ""}
                      {pct(a.drift)}
                    </td>
                    <td className="py-1.5 px-2 text-right text-text-secondary">{formatCurrency(a.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Suggested trades. */}
          {recs.length === 0 ? (
            <p className="text-sm text-text-label">all buckets within tolerance — no rebalancing needed</p>
          ) : (
            <ul className="space-y-2">
              {recs.map((r, i) => (
                <RebalanceRow key={i} rec={r} />
              ))}
            </ul>
          )}
        </div>
      )}
    </Panel>
  )
}

function RebalanceRow({ rec }: { rec: RebalanceRec }) {
  const buy = rec.delta_eur > 0
  return (
    <li className="flex items-start justify-between gap-3 border-b border-border/40 pb-2">
      <div className="min-w-0">
        <span className={`font-mono text-xs uppercase ${rec.priority === "high" ? "text-danger" : "text-warning"}`}>
          {rec.action.replace(/_/g, " ")}
        </span>
        <span className="ml-2 text-sm text-text-secondary">{rec.rationale}</span>
      </div>
      <span className={`shrink-0 font-mono text-sm tabular-nums ${buy ? "text-success" : "text-danger"}`}>
        {buy ? "+" : "−"}
        {formatCurrency(Math.abs(rec.delta_eur))}
      </span>
    </li>
  )
}

function HarvestPanel() {
  const { data, isLoading } = useDecisionHarvest()
  const candidates = data?.candidates ?? []
  const totalSavings = candidates.reduce((s, c) => s + c.tax_savings_estimate, 0)

  return (
    <Panel
      title="tax-loss harvest"
      meta={data ? `${candidates.length} at a loss · ~${formatCurrency(totalSavings)} savings` : undefined}
      statusDotColor={candidates.length > 0 ? "warning" : "muted"}
    >
      {isLoading ? (
        <Skeleton className="h-40" />
      ) : candidates.length === 0 ? (
        <p className="text-sm text-text-label">no positions currently at a loss</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {candidates.map((c) => (
            <li key={c.ticker} className="border-b border-border/40 pb-2">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-accent">{c.ticker}</span>
                <span className="flex items-center gap-3">
                  <NumberDisplay value={c.unrealized_pnl} format="currency" signed />
                  <span className="font-mono text-xs text-text-secondary">
                    ~{formatCurrency(c.tax_savings_estimate)} tax
                  </span>
                </span>
              </div>
              <div className="mt-0.5 flex items-center gap-3 text-xs text-text-label">
                <span>
                  {c.unrealized_pnl_pct.toFixed(1)}% · held {c.holding_days}d
                </span>
              </div>
              {c.warning && <p className="mt-0.5 text-xs text-warning">{c.warning}</p>}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs text-text-label">
        equity losses estimated at ~26.4% Abgeltungsteuer; crypto held &lt; 12mo (Spekulationsfrist).
      </p>
    </Panel>
  )
}

function ConcentrationPanel() {
  const { data, isLoading } = useDecisionAlerts()
  const alerts = data?.alerts ?? []

  return (
    <Panel
      title="concentration alerts"
      meta={data ? `${alerts.length} flagged` : undefined}
      statusDotColor={alerts.some((a) => a.severity === "high") ? "danger" : alerts.length > 0 ? "warning" : "accent"}
    >
      {isLoading ? (
        <Skeleton className="h-40" />
      ) : alerts.length === 0 ? (
        <p className="text-sm text-text-label">no position exceeds its bucket cap</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {alerts.map((a, i) => (
            <li key={i} className="flex items-start gap-2 border-b border-border/40 pb-2">
              <span
                className={`mt-0.5 inline-block h-2 w-2 shrink-0 rounded-full ${
                  severityColor(a.severity) === "danger"
                    ? "bg-danger"
                    : severityColor(a.severity) === "warning"
                      ? "bg-warning"
                      : "bg-text-label"
                }`}
              />
              <div className="min-w-0">
                <span className="font-mono text-accent">{a.ticker}</span>
                <span className="ml-2 font-mono text-xs text-text-secondary">{pct(a.weight)}</span>
                <p className="text-xs text-text-secondary">{a.rationale}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

function SizingPanel() {
  const [score, setScore] = useState(4)
  const suggest = useSuggestSize()
  const [result, setResult] = useState<SizeResponse | null>(null)

  function run(s: number) {
    setScore(s)
    suggest.mutate(s, { onSuccess: (r) => setResult(r) })
  }

  // Compute a sensible default (conviction 4) once on mount.
  const { mutate } = suggest
  useEffect(() => {
    mutate(4, { onSuccess: (r) => setResult(r) })
  }, [mutate])

  return (
    <Panel title="position sizing calculator" meta="conviction → size · section 17" statusDotColor="accent">
      <div className="flex flex-wrap items-center gap-2">
        {[0, 1, 2, 3, 4, 5, 6].map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => run(s)}
            className={`h-9 w-9 rounded-sm border font-mono text-sm tabular-nums transition-colors ${
              score === s
                ? "border-accent bg-accent/10 text-accent"
                : "border-border text-text-secondary hover:border-accent-dim hover:text-text"
            }`}
          >
            {s}
          </button>
        ))}
        <span className="ml-1 text-xs text-text-label">conviction score (0–6)</span>
      </div>

      <div className="mt-4">
        {suggest.isPending ? (
          <Skeleton className="h-16" />
        ) : result ? (
          <div className="flex flex-wrap items-end gap-8">
            <div>
              <div className="label mb-0.5">suggested weight</div>
              <NumberDisplay value={result.weight_pct} format="percent" emphasized className="text-2xl" />
            </div>
            <div>
              <div className="label mb-0.5">eur amount</div>
              <NumberDisplay value={result.eur_amount} format="currency" className="text-2xl" />
            </div>
            <div>
              <div className="label mb-0.5">decision</div>
              <span className={`font-mono text-lg ${result.can_enter ? "text-success" : "text-danger"}`}>
                {result.can_enter ? "can enter" : "no entry"}
              </span>
            </div>
          </div>
        ) : (
          <p className="text-sm text-text-label">pick a conviction score to size a candidate entry</p>
        )}
        {result && <p className="mt-2 text-xs text-text-label">{result.rationale}</p>}
      </div>
    </Panel>
  )
}
