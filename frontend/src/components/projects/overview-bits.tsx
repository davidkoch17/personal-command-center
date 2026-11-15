import { Link } from "react-router-dom"
import { AlarmClock, Hourglass } from "lucide-react"
import { Tag } from "@/components/ui/tag"
import { StatusDot, type StatusColor } from "@/components/ui/status-dot"
import { InlineMd } from "@/components/ui/inline-markdown"
import { cn } from "@/lib/utils"
import { ddmm, type OverviewStatus, type ProjectOverviewCard } from "@/hooks/useProjectOverview"

const STATUS_META: Record<OverviewStatus, { color: StatusColor; label: string }> = {
  active: { color: "success", label: "active" },
  waiting: { color: "warning", label: "waiting" },
  paused: { color: "muted", label: "paused" },
  done: { color: "accent", label: "done" },
}

/** Status pill for an `_overview.md` status (active / waiting / paused / done). */
export function OverviewStatusTag({ status }: { status: OverviewStatus | null }) {
  const meta = status ? STATUS_META[status] : undefined
  const color = meta?.color ?? "muted"
  return (
    <Tag variant={color === "muted" ? "muted" : (color as "success" | "warning" | "accent")}>
      <StatusDot color={color} />
      {meta?.label ?? status ?? "no status"}
    </Tag>
  )
}

/** Small "stale" / "review due" badges. */
export function AttentionBadges({ card }: { card: Pick<ProjectOverviewCard, "stale" | "review_due" | "review_by"> }) {
  return (
    <>
      {card.review_due && (
        <Tag variant="danger" title={`review_by ${card.review_by}`}>
          <AlarmClock className="h-3 w-3" />
          review due
        </Tag>
      )}
      {card.stale && (
        <Tag variant="warning" title="no activity and no file change for more than 21 days">
          <Hourglass className="h-3 w-3" />
          stale
        </Tag>
      )}
    </>
  )
}

/** One project card on the /projects grid. */
export function ProjectOverviewCardView({ card }: { card: ProjectOverviewCard }) {
  return (
    <Link
      to={`/projects/${card.id}`}
      className={cn(
        "panel panel-hover flex flex-col gap-3 transition-colors",
        card.review_due && "border-danger/40",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-text">{card.name}</span>
        <OverviewStatusTag status={card.status} />
      </div>
      {card.next_action ? (
        <p className="line-clamp-3 text-sm text-text-secondary">
          <span className="label mr-1.5">next</span>
          <InlineMd text={card.next_action} />
        </p>
      ) : (
        <p className="text-sm text-text-label">no next action set</p>
      )}
      <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1.5 font-mono text-xs text-text-secondary">
        <span>
          {card.open_count} open · {card.waiting_count} waiting
        </span>
        <span>last {ddmm(card.last_touch)}</span>
        {!card.exists && <span className="text-warning">no _overview.md</span>}
      </div>
      {(card.stale || card.review_due) && (
        <div className="flex flex-wrap gap-1.5">
          <AttentionBadges card={card} />
        </div>
      )}
    </Link>
  )
}
