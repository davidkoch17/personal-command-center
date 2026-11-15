import { Link } from "react-router-dom"
import { FileText, FolderKanban, Lightbulb } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { ProjectOverviewCardView } from "@/components/projects/overview-bits"
import { useProjectOverviews } from "@/hooks/useProjectOverview"
import { cn } from "@/lib/utils"

/**
 * Projects — one card per project folder, fed by its `_overview.md`.
 * The backend already sorts: review due → active → waiting → paused → done.
 * Ideas pipeline / weekly briefing are only small links here, not panels.
 */
export function Projects() {
  const { data, isLoading, isError } = useProjectOverviews()
  const cards = data ?? []
  const active = cards.filter((c) => c.status === "active").length
  const openTotal = cards.reduce((n, c) => n + c.open_count + c.waiting_count, 0)
  const waitingTotal = cards.reduce((n, c) => n + c.waiting_count, 0)
  const reviewDue = cards.filter((c) => c.review_due).length
  const stale = cards.filter((c) => c.stale).length

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="page-title">projects</h1>
        <div className="flex gap-4 font-mono text-xs text-text-secondary">
          <Link to="/ideas" className="inline-flex items-center gap-1 hover:text-accent">
            <Lightbulb className="h-3.5 w-3.5" /> ideas
          </Link>
          <Link to="/todos" className="inline-flex items-center gap-1 hover:text-accent">
            <FileText className="h-3.5 w-3.5" /> to-dos
          </Link>
        </div>
      </div>

      {/* Key figures — all from the _overview.md files */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="aktive projekte" value={isLoading ? "…" : `${active}/${cards.length}`} />
        <Stat
          label="offene punkte"
          value={isLoading ? "…" : String(openTotal)}
          sub={waitingTotal ? `davon ${waitingTotal} wartend` : undefined}
        />
        <Stat label="review fällig" value={isLoading ? "…" : String(reviewDue)} tone={reviewDue ? "danger" : undefined} />
        <Stat label="stale" value={isLoading ? "…" : String(stale)} tone={stale ? "warning" : undefined} sub=">21 Tage still" />
      </div>

      {isError && (
        <Panel title="error" statusDotColor="danger">
          <p className="text-text-secondary">could not load projects. is the backend running?</p>
        </Panel>
      )}

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      ) : cards.length === 0 && !isError ? (
        <EmptyState icon={FolderKanban} message="keine Projektordner gefunden." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {cards.map((c) => (
            <ProjectOverviewCardView key={c.id} card={c} />
          ))}
        </div>
      )}
    </div>
  )
}

function Stat({
  label,
  value,
  sub,
  tone,
}: {
  label: string
  value: string
  sub?: string
  tone?: "danger" | "warning"
}) {
  return (
    <div className="panel flex flex-col gap-1">
      <span className="label">{label}</span>
      <span
        className={cn(
          "text-lg font-semibold tabular-nums text-text",
          tone === "danger" && "text-danger",
          tone === "warning" && "text-warning",
        )}
      >
        {value}
      </span>
      {sub && <span className="text-[11px] text-text-label">{sub}</span>}
    </div>
  )
}
