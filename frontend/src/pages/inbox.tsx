import { Panel } from "@/components/ui/panel"

export function Inbox() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">inbox</h1>
      <Panel title="placeholder" meta="phase 12b">
        <p className="text-text-secondary">content coming in phase 12b</p>
      </Panel>
    </div>
  )
}
