import { useNavigate } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusDot } from "@/components/ui/status-dot"
import { useWatchlistSignals } from "@/hooks/useHome"

/**
 * STATE §2c — watchlist signals: headline bullets from the latest Market Brief
 * (replaces the old active-projects row; projects live in the NOW zone now).
 * Click-through to the Watchlist deep-dive.
 */
export function WatchlistSignals() {
  const { data, isLoading } = useWatchlistSignals()
  const navigate = useNavigate()

  const meta =
    data?.age_days != null
      ? `brief ${data.age_days === 0 ? "today" : `${data.age_days}d ago`}`
      : undefined

  return (
    <Panel title="watchlist signals" meta={meta} statusDotColor="muted">
      {isLoading ? (
        <Skeleton className="h-16" />
      ) : !data || data.signals.length === 0 ? (
        <p className="text-sm text-text-label">no market brief yet</p>
      ) : (
        <div className="space-y-1.5">
          {data.signals.map((s, i) => (
            <button
              key={i}
              type="button"
              onClick={() => navigate("/watchlist")}
              className="flex w-full items-start gap-2 rounded-sm px-1 py-0.5 text-left hover:bg-bg-panel-hover"
            >
              <StatusDot color="accent" />
              <span className="line-clamp-2 text-xs text-text-secondary">{s}</span>
            </button>
          ))}
        </div>
      )}
    </Panel>
  )
}
