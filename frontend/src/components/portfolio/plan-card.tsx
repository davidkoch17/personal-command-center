import { Skeleton } from "@/components/ui/skeleton"
import { Tag } from "@/components/ui/tag"
import { NumberDisplay } from "@/components/ui/number-display"
import { useLatestReport, type ReportSidecar } from "@/hooks/usePortfolioHub"
import { openInOs } from "@/lib/open-in-os"
import { cn } from "@/lib/utils"

/**
 * PositionPlanCard — the single shared store the Watchlist expand + Research tab
 * both render. All fields read from the LATEST stock-analysis sidecar for the
 * ticker (Phase C). When there's no report yet, prompt to run one.
 */
export function PlanCard({ ticker, livePrice }: { ticker: string; livePrice?: number | null }) {
  const { data, isLoading } = useLatestReport(ticker)
  const report = data?.report ?? null

  if (isLoading) return <Skeleton className="h-40" />
  if (!report) {
    return (
      <div className="rounded-sm border border-dashed border-border bg-bg-panel px-3 py-3 text-sm text-text-label">
        no stock-analysis report yet for {ticker}. run one from the research tab to populate the plan card.
      </div>
    )
  }
  return <PlanCardBody report={report} livePrice={livePrice} />
}

function recColor(rec?: string | null): "success" | "danger" | "warning" | "muted" {
  const r = (rec ?? "").toLowerCase()
  if (/(accumulate|buy|add|overweight|long)/.test(r)) return "success"
  if (/(trim|sell|short|avoid|underweight|reduce)/.test(r)) return "danger"
  if (/(hold|neutral|in line)/.test(r)) return "warning"
  return "muted"
}

function PlanCardBody({ report, livePrice }: { report: ReportSidecar; livePrice?: number | null }) {
  // Portfolio is EUR-everywhere (Phase H): prefer the backend's EUR-converted
  // fields; fall back to native only if FX was unavailable at serve time.
  const ccy = report.display_currency ?? "EUR"
  const price =
    report.live_price_eur ?? livePrice ?? report.current_price_at_analysis_eur ?? report.current_price_at_analysis ?? null
  const fvLow = report.fair_value_low_eur ?? report.fair_value_low ?? null
  const fvHigh = report.fair_value_high_eur ?? report.fair_value_high ?? null
  const atAnalysis = report.current_price_at_analysis_eur ?? report.current_price_at_analysis ?? null

  // Upside vs the LIVE EUR price (server-recomputed; else recompute here; else the report's).
  const upLow =
    report.upside_low_pct_eur ?? (price && fvLow ? (fvLow / price - 1) * 100 : report.upside_low_pct ?? null)
  const upHigh =
    report.upside_high_pct_eur ?? (price && fvHigh ? (fvHigh / price - 1) * 100 : report.upside_high_pct ?? null)

  const scenarios = report.scenarios ?? {}
  const fromNative =
    report.native_currency && report.native_currency !== "EUR" ? report.native_currency : null

  return (
    <div className="space-y-3 rounded-sm border border-border bg-bg-panel p-3">
      {/* Header — recommendation + fair value + thesis */}
      <div className="flex flex-wrap items-center gap-2">
        <Tag variant={recColor(report.recommendation)}>{report.recommendation ?? "—"}</Tag>
        <span className="text-xs text-text-label">
          report {report.analysis_date} · {report.skill_label ?? "stock analysis"}
        </span>
        {report.report_path && (
          <button
            type="button"
            onClick={() => openInOs(report.report_path!)}
            className="ml-auto text-xs text-accent hover:underline"
          >
            open full report ↗
          </button>
        )}
      </div>

      {report.thesis_oneliner && (
        <p className="text-sm text-text">{report.thesis_oneliner}</p>
      )}

      {/* Fair value range + upside vs live */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Field label="fair value">
          <span className="font-mono text-sm tabular-nums text-text">
            {fvLow != null && fvHigh != null ? `${fvLow} – ${fvHigh} ${ccy}` : "—"}
          </span>
          {fromNative && (
            <span className="ml-1 text-[10px] text-text-label">
              from {fromNative}
              {report.fx_to_eur != null ? ` @ ${report.fx_to_eur.toFixed(3)}` : ""}
              {report.fx_stale ? " (stale)" : ""}
            </span>
          )}
        </Field>
        <Field label="upside (low–high)">
          <span className="font-mono text-sm tabular-nums">
            {upLow != null && upHigh != null ? (
              <>
                <NumberDisplay value={upLow} format="percent" signed /> …{" "}
                <NumberDisplay value={upHigh} format="percent" signed />
              </>
            ) : (
              "—"
            )}
          </span>
        </Field>
        <Field label={`price ${ccy} (live / @analysis)`}>
          <span className="font-mono text-sm tabular-nums text-text">
            {price != null ? `${price}` : "—"}
            {atAnalysis != null && <span className="text-text-label"> / {atAnalysis}</span>}
          </span>
        </Field>
      </div>

      {/* Scenarios bull/base/bear */}
      {Object.keys(scenarios).length > 0 && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          {(["bull", "base", "bear"] as const).map((k) => {
            const s = scenarios[k]
            if (!s) return null
            const tone = k === "bull" ? "success" : k === "bear" ? "danger" : "warning"
            return (
              <div key={k} className="rounded-sm border border-border px-2 py-1.5">
                <div className="flex items-center justify-between">
                  <span className={cn("label", tone === "success" ? "text-success" : tone === "danger" ? "text-danger" : "text-warning")}>{k}</span>
                  <span className="font-mono text-xs tabular-nums text-text-label">
                    {s.prob != null ? `${Math.round(s.prob * 100)}%` : ""}
                  </span>
                </div>
                <div className="font-mono text-sm tabular-nums text-text">
                  {s.implied_value_eur ?? s.implied_value ?? "—"}
                </div>
                {s.note && <div className="mt-0.5 line-clamp-2 text-xs text-text-label">{s.note}</div>}
              </div>
            )
          })}
        </div>
      )}

      {/* Monitorables · thesis-break · catalysts */}
      <div className="grid gap-3 sm:grid-cols-3">
        <ChipList label="monitorables" items={report.monitorables ?? []} tone="text-text-secondary" />
        <ChipList label="thesis-break triggers" items={report.thesis_break_triggers ?? []} tone="text-danger" />
        <CatalystList catalysts={report.catalysts ?? []} />
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="label mb-0.5">{label}</div>
      {children}
    </div>
  )
}

function ChipList({ label, items, tone }: { label: string; items: string[]; tone: string }) {
  return (
    <div>
      <div className="label mb-1">{label}</div>
      {items.length === 0 ? (
        <p className="text-xs text-text-label">—</p>
      ) : (
        <ul className="space-y-0.5">
          {items.map((it, i) => (
            <li key={i} className={cn("text-xs", tone)}>• {it}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function CatalystList({ catalysts }: { catalysts: { label: string; date?: string }[] }) {
  return (
    <div>
      <div className="label mb-1">catalysts (incl. next earnings)</div>
      {catalysts.length === 0 ? (
        <p className="text-xs text-text-label">—</p>
      ) : (
        <ul className="space-y-0.5">
          {catalysts.map((c, i) => (
            <li key={i} className="text-xs text-text-secondary">
              • {c.label}
              {c.date && <span className="font-mono text-text-label"> · {c.date}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
