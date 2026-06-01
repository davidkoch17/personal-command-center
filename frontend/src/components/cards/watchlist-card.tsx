import { ArrowUpRight } from "lucide-react"
import type { WatchlistEntry } from "@/hooks/useFinance"
import { NumberDisplay } from "@/components/ui/number-display"
import { Tag } from "@/components/ui/tag"
import { daysUntil } from "@/lib/status"
import { cn } from "@/lib/utils"

/** Days since an ISO added-date (negative of daysUntil), or null. */
function daysOnWatchlist(added?: string | null): number | null {
  const d = daysUntil(added)
  return d == null ? null : -d
}

export function WatchlistCard({ entry }: { entry: WatchlistEntry }) {
  const days = daysOnWatchlist(entry.added)
  return (
    <a
      href={`/workspace/watchlist/${encodeURIComponent(entry.ticker)}`}
      target="_blank"
      rel="noopener noreferrer"
      className={cn("panel panel-hover group flex flex-col gap-3 transition-colors")}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="font-mono text-sm font-medium text-text">{entry.ticker}</div>
          <div className="truncate text-xs text-text-secondary">{entry.name || "—"}</div>
        </div>
        <ArrowUpRight className="h-4 w-4 shrink-0 text-text-label group-hover:text-accent transition-colors" />
      </div>

      <div className="flex items-end justify-between gap-2">
        <div>
          <div className="label mb-0.5">close</div>
          <NumberDisplay value={entry.price?.last_close ?? null} format="currency" />
        </div>
        <div className="text-right">
          <div className="label mb-0.5">1w</div>
          <NumberDisplay value={entry.price?.week_change_pct ?? null} format="percent" signed />
        </div>
      </div>

      <div className="mt-auto flex items-center justify-between gap-2">
        <Tag variant="muted">{entry.status || "—"}</Tag>
        <span className="font-mono text-xs text-text-label">
          {days != null ? `${days}d on list` : ""}
        </span>
      </div>
    </a>
  )
}
