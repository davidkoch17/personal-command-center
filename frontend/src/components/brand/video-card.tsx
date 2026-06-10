import { ArrowRight, ArrowUpRight } from "lucide-react"
import type { VideoCard as VideoCardData } from "@/hooks/useBrand"
import { cn } from "@/lib/utils"

interface VideoCardProps {
  video: VideoCardData
  /** All pipeline stages, for the move dropdown. */
  stages: string[]
  /** Move this video to an arbitrary stage (kanban move, both directions). */
  onMove: (stage: string) => void
  /** Quick-advance to the next stage. Omit on the last (PUBLISHED) column. */
  onAdvance?: () => void
  /** Disable controls while a move is in flight. */
  busy?: boolean
}

/** Kanban card for one video. Title links to the workspace (new tab). */
export function VideoCard({ video, stages, onMove, onAdvance, busy }: VideoCardProps) {
  const touched = video.modified?.slice(0, 10) ?? ""
  return (
    <div className="panel panel-hover flex flex-col gap-2 p-3 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <a
          href={`/workspace/brand/${encodeURIComponent(video.name)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="group flex items-start gap-1 min-w-0"
        >
          <span className="truncate text-sm font-medium text-text group-hover:text-accent">
            {video.title}
          </span>
          <ArrowUpRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-label group-hover:text-accent" />
        </a>
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[11px] text-text-secondary">
          {video.platform || "—"}
        </span>
        <span className="font-mono text-[11px] text-text-label">{touched}</span>
      </div>

      {/* Move to any stage (real kanban move). */}
      <select
        aria-label="move to stage"
        value={video.stage}
        disabled={busy}
        onChange={(e) => {
          if (e.target.value !== video.stage) onMove(e.target.value)
        }}
        className={cn(
          "w-full rounded-sm border border-border bg-bg-panel px-2 py-1",
          "font-mono text-[11px] text-text-secondary",
          "hover:border-accent-dim focus:border-accent focus:outline-none",
          "disabled:opacity-50",
        )}
      >
        {stages.map((s) => (
          <option key={s} value={s}>
            {s.toLowerCase()}
          </option>
        ))}
      </select>

      {onAdvance && (
        <button
          type="button"
          onClick={onAdvance}
          disabled={busy}
          className={cn(
            "flex items-center justify-center gap-1 rounded-sm border border-border py-1",
            "text-xs text-text-secondary hover:border-accent-dim hover:text-text",
            "disabled:opacity-50",
          )}
        >
          next stage <ArrowRight className="h-3 w-3" />
        </button>
      )}
    </div>
  )
}
