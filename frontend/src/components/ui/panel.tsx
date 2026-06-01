import { ReactNode } from "react"
import { cn } from "@/lib/utils"
import { StatusDot, type StatusColor } from "./status-dot"

interface PanelProps {
  title?: string
  meta?: string // top-right metadata
  statusDotColor?: StatusColor
  children: ReactNode
  className?: string
}

/**
 * Bordered content panel — the core Cockpit container. Header shows a small
 * status dot + lowercase label on the left and optional monospace metadata on
 * the right. Everything in the UI lives inside a panel; no floating text.
 */
export function Panel({
  title,
  meta,
  statusDotColor = "muted",
  children,
  className,
}: PanelProps) {
  return (
    <div className={cn("panel", className)}>
      {(title || meta) && (
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {title && <StatusDot color={statusDotColor} />}
            {title && <span className="label">{title}</span>}
          </div>
          {meta && (
            <span className="text-text-secondary text-xs font-mono">{meta}</span>
          )}
        </div>
      )}
      {children}
    </div>
  )
}
