import { FolderKanban } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { ProjectOverviewCardView } from "@/components/projects/overview-bits"
import { useProjectOverviews } from "@/hooks/useProjectOverview"

/**
 * Projects — one card per project folder, fed by its `_overview.md`.
 * The backend already sorts: review due → active → waiting → paused → done.
 */
export function Projects() {
  const { data, isLoading, isError } = useProjectOverviews()
  const cards = data ?? []
  const attention = cards.filter((c) => c.stale || c.review_due).length

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="page-title">projects</h1>
        {!isLoading && cards.length > 0 && (
          <span className="font-mono text-xs text-text-secondary">
            {cards.length} projekte{attention > 0 ? ` · ${attention} brauchen Aufmerksamkeit` : ""}
          </span>
        )}
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
