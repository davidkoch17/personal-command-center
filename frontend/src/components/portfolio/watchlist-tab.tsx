import { useMemo, useState } from "react"
import { ChevronRight } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { Tag } from "@/components/ui/tag"
import { NumberDisplay } from "@/components/ui/number-display"
import { useWatchlist, type WatchlistEntry } from "@/hooks/useFinance"
import { useCaptureRadar } from "@/hooks/usePortfolioHub"
import { PlanCard } from "./plan-card"
import { ConnectedNews } from "./connected-news"
import { cn } from "@/lib/utils"

const TIERS = ["Tier 1", "Tier 2", "Tier 3"] as const

export function WatchlistTab() {
  const wl = useWatchlist(true)
  const radar = useCaptureRadar()

  const byTier = useMemo(() => {
    const map: Record<string, WatchlistEntry[]> = {}
    for (const [tier, entries] of Object.entries(wl.data?.tiers ?? {})) {
      const key = TIERS.find((t) => tier.includes(t.replace("Tier ", ""))) ?? "Tier 3"
      map[key] = (map[key] ?? []).concat(entries)
    }
    return map
  }, [wl.data])

  return (
    <div className="space-y-5">
      {/* Global radar card (Option C) — what changed since last review */}
      <GlobalRadarCard />

      {wl.isLoading ? (
        <Skeleton className="h-48" />
      ) : (
        TIERS.map((tier) => {
          const entries = (byTier[tier] ?? []).filter((e) => e.ticker)
          if (entries.length === 0) return null
          return (
            <Panel key={tier} title={tier.toLowerCase()} meta={`${entries.length} names`} statusDotColor="accent">
              <div className="space-y-1.5">
                {entries.map((e) => (
                  <WatchlistRow
                    key={e.ticker}
                    entry={e}
                    captureCount={radar.data?.ticker_counts?.[e.ticker.toUpperCase()] ?? 0}
                  />
                ))}
              </div>
            </Panel>
          )
        })
      )}
    </div>
  )
}

function GlobalRadarCard() {
  const { data, isLoading } = useCaptureRadar()
  return (
    <Panel title="watchlist radar — captures by sector" statusDotColor="accent"
      meta={data ? `${data.sectors.reduce((a, s) => a + s.count, 0)} captures` : undefined}>
      {isLoading ? (
        <Skeleton className="h-12" />
      ) : !data?.sectors.length ? (
        <p className="text-sm text-text-label">no captures linked yet — the capture pipeline feeds this.</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {data.sectors.map((s) => (
            <span key={s.sector} className="inline-flex items-center gap-1.5 rounded-sm border border-border bg-bg px-2.5 py-1 text-sm">
              <span className="text-text-secondary">{s.sector}</span>
              <span className="font-mono tabular-nums text-accent">{s.count}</span>
            </span>
          ))}
        </div>
      )}
    </Panel>
  )
}

function WatchlistRow({ entry, captureCount }: { entry: WatchlistEntry; captureCount: number }) {
  const [open, setOpen] = useState(false)
  const ticker = entry.ticker.toUpperCase()
  const dayPct = entry.price?.week_change_pct ?? null

  return (
    <div className="rounded-sm border border-border/60">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-bg-panel-hover"
      >
        <ChevronRight className={cn("h-4 w-4 shrink-0 text-text-label transition-transform", open && "rotate-90")} />
        <div className="min-w-0 flex-1">
          <span className="font-mono text-sm text-text">{ticker}</span>
          <span className="ml-2 truncate text-xs text-text-secondary">{entry.name}</span>
        </div>
        {captureCount > 0 && (
          <Tag variant="accent">{captureCount} news</Tag>
        )}
        <span className="w-20 text-right">
          <NumberDisplay value={entry.price?.last_close ?? null} format="currency" />
        </span>
        <span className="w-16 text-right">
          <NumberDisplay value={dayPct} format="percent" signed />
        </span>
      </button>

      {open && (
        <div className="space-y-3 border-t border-border/60 px-3 py-3">
          {/* Plan & thesis card — shared store (stock-analysis sidecar) */}
          <PlanCard ticker={ticker} livePrice={entry.price?.last_close ?? null} />
          {/* Connected news (sector summary -> big moves -> full list) */}
          <ConnectedNews ticker={ticker} enabled={open} />
        </div>
      )}
    </div>
  )
}
