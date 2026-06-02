import { useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { Menu } from "lucide-react"
import { StatusDot, type StatusColor } from "@/components/ui/status-dot"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useSystemStatus } from "@/hooks/useSystem"
import { isoDate } from "@/lib/utils"
import { JarvisBall } from "@/components/jarvis/jarvis-ball"
import { useJarvisBriefing } from "@/hooks/useJarvisBriefing"

interface IntegrationCheck {
  name?: string
  status?: string
}

/** Roll integration checks up to a single health color + label. */
function aggregateHealth(checks: IntegrationCheck[] | undefined): {
  color: StatusColor
  label: string
} {
  if (!checks || checks.length === 0) return { color: "muted", label: "status unknown" }
  const statuses = checks.map((c) => (c.status ?? "").toLowerCase())
  if (statuses.some((s) => s === "error")) return { color: "danger", label: "an integration errored" }
  if (statuses.some((s) => s === "not_configured"))
    return { color: "warning", label: "some integrations not configured" }
  return { color: "success", label: "all integrations ok" }
}

/**
 * Top header: hamburger (mobile) + app name on the left; aggregate system-status
 * dot (click → settings diagnostics), the current date, and the small Jarvis
 * ball on the right. The ball runs the same briefing flow as the Home one (its
 * own hook instance); a short subtitle appears beside it while it's active.
 */
export function Header({ onMenuClick }: { onMenuClick: () => void }) {
  const navigate = useNavigate()
  const { data } = useSystemStatus()
  const today = isoDate()
  const jarvis = useJarvisBriefing()

  const health = useMemo(
    () => aggregateHealth(data?.integrations as IntegrationCheck[] | undefined),
    [data],
  )

  return (
    <header className="no-print flex h-12 shrink-0 items-center justify-between border-b border-border bg-bg-panel px-4 sm:px-6">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onMenuClick}
          aria-label="open navigation"
          className="min-[800px]:hidden text-text-secondary hover:text-text"
        >
          <Menu className="h-5 w-5" />
        </button>
        <span className="text-sm font-semibold tracking-tight lowercase">command center</span>
      </div>

      <div className="flex items-center gap-4">
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={() => navigate("/settings")}
              aria-label={`system status: ${health.label}`}
              className="flex items-center"
            >
              <StatusDot color={health.color} />
            </button>
          </TooltipTrigger>
          <TooltipContent>{health.label} · diagnostics →</TooltipContent>
        </Tooltip>
        <span className="font-mono text-xs text-text-secondary tabular-nums">{today}</span>
        {/* Small Jarvis ball — runs the briefing flow from any page. Subtitle
            shows beside it (≥sm) while active; the small ball is otherwise quiet. */}
        {jarvis.subtitle && (
          <span className="hidden max-w-[180px] truncate font-mono text-[11px] uppercase tracking-wider text-text-secondary animate-fade-in sm:inline">
            {jarvis.subtitle}
          </span>
        )}
        <JarvisBall
          size="small"
          state={jarvis.state}
          onClick={jarvis.trigger}
          className="h-9 w-9"
        />
      </div>
    </header>
  )
}
