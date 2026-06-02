import { useNavigate } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useDecisions,
  useHitRate,
  useCryptoHoldingPeriods,
} from "@/hooks/useFinance"

function daysAgo(iso: string): number {
  const d = new Date(iso + "T00:00:00")
  return Math.floor((Date.now() - d.getTime()) / 86_400_000)
}

/**
 * Home behavioral nudges — decisions logged this week, hypothesis hit rate this
 * quarter, and the next crypto Spekulationsfrist landing. Clicking opens the
 * decision journal.
 */
export function BehavioralNudges() {
  const decisions = useDecisions(200)
  const hitRate = useHitRate(4)
  const crypto = useCryptoHoldingPeriods()
  const navigate = useNavigate()

  const loading = decisions.isLoading || hitRate.isLoading || crypto.isLoading

  const thisWeek = (decisions.data?.decisions ?? []).filter(
    (d) => d.date && daysAgo(d.date) <= 7,
  ).length

  const hr = hitRate.data
  const hitRatePct = hr?.hit_rate != null ? `${(hr.hit_rate * 100).toFixed(0)}%` : "—"

  // Soonest crypto landing among names not yet tax-free.
  const pending = crypto.data.filter((c) => c.available && !c.is_tax_free && c.days_to_tax_free != null)
  const next = pending.length
    ? pending.reduce((a, b) => ((a.days_to_tax_free ?? 0) <= (b.days_to_tax_free ?? 0) ? a : b))
    : null

  return (
    <Panel title="behavioral" meta="decisions · hit rate · spekulationsfrist" statusDotColor="muted">
      {loading ? (
        <Skeleton className="h-16" />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Nudge
            label="decisions this week"
            value={String(thisWeek)}
            sub={decisions.data ? `${decisions.data.count} logged total` : ""}
            onClick={() => navigate("/decision-journal")}
          />
          <Nudge
            label="hypothesis hit rate"
            value={hitRatePct}
            sub={hr && hr.hypotheses_reviewed > 0 ? `${hr.confirmed}/${hr.hypotheses_reviewed} confirmed` : "no closed yet"}
            onClick={() => navigate("/decision-journal")}
          />
          <Nudge
            label="next crypto tax-free"
            value={next ? `${next.days_to_tax_free}d` : pending.length === 0 && crypto.data.length > 0 ? "all free" : "—"}
            sub={next ? `${next.ticker} · ${next.tax_free_date}` : crypto.data.length === 0 ? "no crypto" : "Spekulationsfrist passed"}
            onClick={() => navigate("/workspace/money")}
          />
        </div>
      )}
    </Panel>
  )
}

function Nudge({
  label,
  value,
  sub,
  onClick,
}: {
  label: string
  value: string
  sub: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-sm border border-border bg-bg-panel px-3 py-2 text-left transition-colors hover:border-accent-dim"
    >
      <div className="label mb-0.5">{label}</div>
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-2xl font-medium tabular-nums text-text">{value}</span>
        <span className="truncate text-xs text-text-secondary">{sub}</span>
      </div>
    </button>
  )
}
