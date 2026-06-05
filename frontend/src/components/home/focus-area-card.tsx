import { useNavigate } from "react-router-dom"
import { ArrowUpRight } from "lucide-react"
import { StatusDot, type StatusColor } from "@/components/ui/status-dot"
import type { FocusArea } from "@/hooks/useHome"

const DOT: Record<FocusArea["status"], StatusColor> = {
  green: "success",
  yellow: "warning",
  red: "danger",
}

/**
 * One NOW-zone focus area card (Home_Redesign_Spec.md §1a): bold title, status
 * dot, one-line next action, time indicator. Clicking opens the relevant page
 * in-app, or the project workspace in a new tab (Cockpit deep-dive pattern).
 */
export function FocusAreaCard({ card }: { card: FocusArea }) {
  const navigate = useNavigate()

  const body = (
    <>
      <div className="flex items-start justify-between gap-1.5">
        <div className="flex min-w-0 items-center gap-1.5">
          <StatusDot color={DOT[card.status]} />
          <span className="truncate text-sm font-semibold text-text">{card.title}</span>
        </div>
        <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-text-label transition-colors group-hover:text-accent" />
      </div>
      <p className="line-clamp-2 text-xs text-text-secondary">{card.next_action}</p>
      {card.time_indicator && (
        <span className="mt-auto font-mono text-xs text-accent tabular-nums">
          {card.time_indicator}
        </span>
      )}
    </>
  )

  const cls =
    "panel panel-hover group flex min-h-[6.5rem] flex-col gap-1.5 p-3 text-left transition-colors"

  // Workspace deep-dives open in a NEW TAB; regular pages navigate in-app.
  return card.new_tab ? (
    <a href={card.target} target="_blank" rel="noopener noreferrer" className={cls}>
      {body}
    </a>
  ) : (
    <button type="button" onClick={() => navigate(card.target)} className={cls}>
      {body}
    </button>
  )
}
