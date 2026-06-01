import { Link, useParams } from "react-router-dom"
import { Panel } from "@/components/ui/panel"

export function ProjectWorkspace() {
  const { id } = useParams<{ id: string }>()
  return (
    <div className="min-h-screen bg-bg text-text p-6">
      <div className="mx-auto max-w-[1400px] space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">
            project workspace
          </h1>
          <Link
            to="/projects"
            className="font-mono text-xs text-text-secondary hover:text-accent"
          >
            ← projects
          </Link>
        </div>
        <Panel title="placeholder" meta={`id: ${id ?? "—"}`}>
          <p className="text-text-secondary">deep-dive workspace — content coming in phase 12c</p>
        </Panel>
      </div>
    </div>
  )
}
