import type { ReactNode } from "react"
import { useNavigate } from "react-router-dom"
import { ArrowUp, ArrowUpRight, BookOpen, CalendarCheck } from "lucide-react"
import { StatusDot, type StatusColor } from "@/components/ui/status-dot"
import { useBrainSystem, type BrainSystemResponse } from "@/hooks/useHome"
import { Skeleton } from "@/components/ui/skeleton"

/**
 * Brain/System focus card with real data (Brain_System_Card_Spec.md):
 * pending vault upgrades + reading status + weekly review countdown. Replaces
 * the generic FocusAreaCard for the "brain" slot in the NOW zone.
 *
 * Status dot: 🟢 review not overdue + reading fresh (≤7d) · 🟡 either overdue
 * or stale >7d · 🔴 both overdue and stale >14d · ⚪ no data sources at all.
 * Click target: /settings (until a /system page exists).
 */
export function BrainSystemCard() {
  const { data, isLoading } = useBrainSystem()
  const navigate = useNavigate()

  if (isLoading) return <Skeleton className="min-h-[6.5rem]" />

  const noData = !data || (!data.pending_upgrades && !data.reading && !data.weekly_review)

  return (
    <button
      type="button"
      onClick={() => navigate("/settings")}
      className="panel panel-hover group flex min-h-[6.5rem] flex-col gap-1.5 p-3 text-left transition-colors"
    >
      <div className="flex items-start justify-between gap-1.5">
        <div className="flex min-w-0 items-center gap-1.5">
          <StatusDot color={statusColor(data)} />
          <span className="truncate text-sm font-semibold text-text">Brain / System</span>
        </div>
        <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-text-label transition-colors group-hover:text-accent" />
      </div>

      {noData ? (
        <p className="text-xs text-text-label">no data yet</p>
      ) : (
        <div className="space-y-1">
          <Line icon={<ArrowUp className="h-3 w-3" />}>
            {data.pending_upgrades
              ? `${data.pending_upgrades.count} upgrades pending` +
                (data.pending_upgrades.top[0] ? `: ${data.pending_upgrades.top[0].title}` : "")
              : "? upgrades pending"}
          </Line>
          <Line icon={<BookOpen className="h-3 w-3" />}>
            {data.reading
              ? data.reading.current_book +
                (data.reading.stale_days != null ? ` · ${data.reading.stale_days}d ago` : "")
              : "no book tracked"}
          </Line>
          <Line icon={<CalendarCheck className="h-3 w-3" />}>
            {reviewLabel(data.weekly_review)}
          </Line>
        </div>
      )}
    </button>
  )
}

function Line({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <div className="flex items-start gap-1.5 text-xs text-text-secondary">
      <span className="mt-0.5 shrink-0 text-text-label">{icon}</span>
      <span className="line-clamp-1">{children}</span>
    </div>
  )
}

function reviewLabel(wr: BrainSystemResponse["weekly_review"] | null | undefined): ReactNode {
  if (!wr) return "weekly review: —"
  if (wr.overdue && wr.days_since != null) {
    return (
      <>
        weekly review:{" "}
        <span className="rounded-sm bg-warning/15 px-1 font-mono text-warning">
          overdue {wr.days_since}d
        </span>
      </>
    )
  }
  const countdown = wr.days_until_next === 0 ? "today" : `in ${wr.days_until_next}d`
  return wr.last_review_date
    ? `weekly review: ${countdown}`
    : `weekly review: first one due ${countdown}`
}

function statusColor(data: BrainSystemResponse | undefined): StatusColor {
  if (!data || (!data.pending_upgrades && !data.reading && !data.weekly_review)) return "muted"
  const overdue = data.weekly_review?.overdue ?? false
  const staleDays = data.reading?.stale_days
  const stale7 = staleDays != null && staleDays > 7
  const stale14 = staleDays != null && staleDays > 14
  if (overdue && stale14) return "danger"
  if (overdue || stale7) return "warning"
  return "success"
}
