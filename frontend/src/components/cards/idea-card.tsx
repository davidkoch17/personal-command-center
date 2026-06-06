import { ArrowUpRight } from "lucide-react"
import type { IdeaCard as IdeaCardData } from "@/lib/types"
import { StageStrip } from "@/components/cards/stage-strip"
import { StatusDot } from "@/components/ui/status-dot"
import { cn } from "@/lib/utils"

const TOTAL_STAGES = 12

interface IdeaCardProps {
  idea: IdeaCardData
  className?: string
}

/** Pull a best-effort string field out of the free-form idea `state` dict. */
function stateField(state: Record<string, unknown>, ...keys: string[]): string | null {
  for (const k of keys) {
    const v = state?.[k]
    if (v != null && v !== "") return String(v)
  }
  return null
}

/**
 * Idea summary card with a 12-dot validation-progress strip. Opens the idea
 * workspace in a new tab.
 */
export function IdeaCard({ idea, className }: IdeaCardProps) {
  const score = stateField(idea.state, "score", "total_score")
  const recommendation = stateField(idea.state, "recommendation", "verdict")
  // Runner's live marker — present in _state.json while a stage is in flight.
  const running = idea.state?.["_running"] != null

  return (
    <a
      href={`/workspace/idea/${encodeURIComponent(idea.name)}`}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "panel panel-hover group flex flex-col gap-3 transition-colors",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="truncate text-sm font-medium text-text">
          {idea.name}
        </span>
        <ArrowUpRight className="h-4 w-4 shrink-0 text-text-label group-hover:text-accent transition-colors" />
      </div>

      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <span className="label">validation</span>
          <span className="flex items-center gap-1.5 font-mono text-xs text-text-secondary">
            {running && (
              <>
                <StatusDot color="accent" pulse />
                <span className="text-accent">running</span>
              </>
            )}
            {Math.min(idea.stages_complete, TOTAL_STAGES)}/{TOTAL_STAGES}
          </span>
        </div>
        <StageStrip complete={idea.stages_complete} total={TOTAL_STAGES} />
      </div>

      <div className="flex items-center justify-between text-sm">
        <div>
          <div className="label mb-0.5">score</div>
          <span className="font-mono text-text">{score ?? "—"}</span>
        </div>
        <div className="text-right">
          <div className="label mb-0.5">recommendation</div>
          <span className="text-text-secondary">{recommendation ?? "—"}</span>
        </div>
      </div>
    </a>
  )
}
