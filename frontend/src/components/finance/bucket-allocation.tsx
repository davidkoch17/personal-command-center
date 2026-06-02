import { AlertTriangle } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { useBuckets, type BucketRow } from "@/hooks/useFinance"
import { cn, formatCurrency } from "@/lib/utils"

/** Per-bucket segment color (matches the cockpit categorical ramp). */
const BUCKET_COLOR: Record<string, string> = {
  etf_foundation: "#2563EB",
  single_stocks: "#14B8A6",
  crypto: "#F59E0B",
  wild_cards: "#A855F7",
}

const STATUS_TEXT: Record<BucketRow["status"], string> = {
  ok: "text-success",
  warn: "text-warning",
  alert: "text-danger",
}
const STATUS_DOT: Record<BucketRow["status"], string> = {
  ok: "bg-success",
  warn: "bg-warning",
  alert: "bg-danger",
}

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`
}
function signedPct(v: number): string {
  return `${v > 0 ? "+" : ""}${(v * 100).toFixed(1)}pp`
}

/**
 * 4-bucket allocation view (Investment_Philosophy.md § 0). Shows a stacked
 * current-allocation bar, per-bucket drift vs target, and trigger alerts.
 * `compact` trims it for the Home page block.
 */
export function BucketAllocation({ compact = false }: { compact?: boolean }) {
  const { data, isLoading } = useBuckets()

  if (isLoading) return <Skeleton className="h-40" />
  if (!data) return <p className="text-sm text-text-label">no allocation data</p>

  const { buckets, alerts, total_value } = data

  return (
    <Panel
      title="bucket allocation"
      meta={total_value > 0 ? formatCurrency(total_value) : undefined}
      statusDotColor={alerts.length > 0 ? "warning" : "accent"}
    >
      {/* Stacked current-allocation bar. */}
      <div className="mb-3 flex h-5 w-full overflow-hidden rounded-sm border border-border">
        {buckets.map((b) =>
          b.current_weight > 0 ? (
            <div
              key={b.bucket}
              style={{ width: `${b.current_weight * 100}%`, backgroundColor: BUCKET_COLOR[b.bucket] }}
              title={`${b.label}: ${pct(b.current_weight)}`}
            />
          ) : null,
        )}
        {total_value === 0 && <div className="w-full bg-bg-panel-hover" />}
      </div>

      {/* Per-bucket rows: current vs target + drift. */}
      <div className={cn("grid gap-2", compact ? "grid-cols-2" : "grid-cols-2 md:grid-cols-4")}>
        {buckets.map((b) => (
          <div key={b.bucket} className="rounded-sm border border-border bg-bg-panel p-2.5">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: BUCKET_COLOR[b.bucket] }} />
              <span className="truncate text-xs text-text-secondary">{b.label}</span>
            </div>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span className="font-mono text-lg font-medium tabular-nums text-text">{pct(b.current_weight)}</span>
              <span className="font-mono text-[10px] text-text-label">/ {pct(b.target_weight)}</span>
            </div>
            <div className="mt-0.5 flex items-center gap-1.5">
              <span className={cn("h-1.5 w-1.5 rounded-full", STATUS_DOT[b.status])} />
              <span className={cn("font-mono text-[10px] tabular-nums", STATUS_TEXT[b.status])}>
                {signedPct(b.drift)}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Trigger alerts. */}
      {alerts.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {alerts.map((a, i) => (
            <div key={i} className="flex items-start gap-2 rounded-sm border border-warning/30 bg-warning/5 px-2.5 py-1.5">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
              <span className="text-xs text-text-secondary">{a.message}</span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  )
}
