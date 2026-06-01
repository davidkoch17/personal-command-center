import { StatusDot, type StatusColor } from "@/components/ui/status-dot"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { isoDate } from "@/lib/utils"

/**
 * System status indicators shown in the header. Phase 12a renders static
 * placeholder health — later phases wire these to live integration checks.
 */
const SYSTEM_STATUS: { label: string; color: StatusColor }[] = [
  { label: "backend", color: "muted" },
  { label: "vault", color: "muted" },
  { label: "market data", color: "muted" },
]

/**
 * Top header bar: app name on the left, integration health dots and the current
 * date (monospace YYYY-MM-DD) on the right.
 */
export function Header() {
  const today = isoDate()

  return (
    <header className="flex items-center justify-between border-b border-border bg-bg-panel px-6 h-12 shrink-0">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold tracking-tight lowercase">
          command center
        </span>
      </div>

      <div className="flex items-center gap-5">
        <div className="flex items-center gap-3">
          {SYSTEM_STATUS.map((s) => (
            <Tooltip key={s.label}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="flex items-center"
                  aria-label={`${s.label} status`}
                >
                  <StatusDot color={s.color} />
                </button>
              </TooltipTrigger>
              <TooltipContent>{s.label}</TooltipContent>
            </Tooltip>
          ))}
        </div>
        <span className="font-mono text-xs text-text-secondary tabular-nums">
          {today}
        </span>
      </div>
    </header>
  )
}
