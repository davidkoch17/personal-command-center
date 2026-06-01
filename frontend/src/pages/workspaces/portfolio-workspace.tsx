import { Link } from "react-router-dom"
import { Panel } from "@/components/ui/panel"

export function PortfolioWorkspace() {
  return (
    <div className="min-h-screen bg-bg text-text p-6">
      <div className="mx-auto max-w-[1400px] space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">
            portfolio workspace
          </h1>
          <Link
            to="/portfolio"
            className="font-mono text-xs text-text-secondary hover:text-accent"
          >
            ← portfolio
          </Link>
        </div>
        <Panel title="placeholder" meta="phase 12d">
          <p className="text-text-secondary">deep-dive workspace — content coming in phase 12d</p>
        </Panel>
      </div>
    </div>
  )
}
