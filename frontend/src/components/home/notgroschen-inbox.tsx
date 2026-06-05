import { useNavigate } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { NumberDisplay } from "@/components/ui/number-display"
import { useNotgroschen } from "@/hooks/useHome"
import { useInbox } from "@/hooks/useInbox"
import { formatCurrency } from "@/lib/utils"

/**
 * STATE §2d — Notgroschen progress + inbox triage count.
 * Phase 1 (Tagesgeld < €4,000): progress bar toward the €4,000 target.
 * Phase 2 (>= €4,000): switches to the depot funding view (cumulative invested).
 */
export function NotgroschenInbox() {
  const notgroschen = useNotgroschen()
  const inbox = useInbox()
  const navigate = useNavigate()
  const data = notgroschen.data

  const inboxCount = inbox.data?.length ?? 0

  return (
    <Panel
      title="notgroschen · inbox"
      statusDotColor={inboxCount > 0 ? "warning" : "success"}
    >
      {notgroschen.isLoading ? (
        <Skeleton className="h-16" />
      ) : (
        <button
          type="button"
          onClick={() => navigate("/money")}
          className="block w-full rounded-sm text-left hover:bg-bg-panel-hover"
        >
          {data?.phase === 2 ? (
            <>
              <div className="label mb-0.5">notgroschen full — depot funding</div>
              <NumberDisplay
                value={data.depot_invested}
                format="currency"
                emphasized
                className="text-xl"
              />
              <span className="ml-2 text-xs text-text-secondary">invested</span>
            </>
          ) : (
            <>
              <div className="mb-1 flex items-baseline justify-between">
                <span className="label">notgroschen</span>
                <span className="font-mono text-xs text-text-secondary tabular-nums">
                  {data?.cash_balance != null ? formatCurrency(data.cash_balance) : "—"} /{" "}
                  {formatCurrency(data?.target ?? 4000)}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-bg-panel-hover">
                <div
                  className="h-full rounded-full bg-accent transition-all"
                  style={{ width: `${Math.round((data?.pct ?? 0) * 100)}%` }}
                />
              </div>
              <div className="mt-1 font-mono text-xs text-text-secondary tabular-nums">
                {Math.round((data?.pct ?? 0) * 100)}%
              </div>
            </>
          )}
        </button>
      )}

      <button
        type="button"
        onClick={() => navigate("/inbox")}
        className="mt-3 flex w-full items-baseline justify-between rounded-sm border-t border-border pt-2 text-left hover:bg-bg-panel-hover"
      >
        <span className="label">inbox</span>
        <span className="text-xs text-text-secondary">
          {inboxCount === 0 ? "inbox zero" : `${inboxCount} items to triage`}
        </span>
      </button>
    </Panel>
  )
}
