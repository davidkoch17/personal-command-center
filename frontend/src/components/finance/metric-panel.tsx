import type { ReactNode } from "react"
import { Panel } from "@/components/ui/panel"
import type { StatusColor } from "@/components/ui/status-dot"

interface MetricPanelProps {
  label: string
  value: ReactNode
  caption?: ReactNode
  dotColor?: StatusColor
}

/** Compact metric tile for the finance overview rows. */
export function MetricPanel({ label, value, caption, dotColor = "accent" }: MetricPanelProps) {
  return (
    <Panel title={label} statusDotColor={dotColor}>
      <div className="text-2xl">{value}</div>
      {caption && <div className="mt-1 text-xs text-text-secondary">{caption}</div>}
    </Panel>
  )
}
