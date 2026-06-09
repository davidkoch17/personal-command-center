import { useDraggable } from "@dnd-kit/core"
import { GripVertical, Layers } from "lucide-react"
import {
  BLOCK_PROJECTS,
  blockColor,
  formatDuration,
  type DeepWorkBlock,
} from "@/lib/planner"

/** The in-progress block definition the creator edits (id/color derived later). */
export type BlockDraft = Pick<DeepWorkBlock, "project" | "title" | "duration_min">

const DURATIONS = [30, 60, 90, 120, 180, 240]

interface DeepWorkCreatorProps {
  draft: BlockDraft
  onChange: (draft: BlockDraft) => void
  disabled?: boolean
}

/**
 * Builds a deep-work block (project + duration + optional title) and exposes it
 * as a draggable chip. Dropping the chip on a day column creates the block there
 * (handled by the page's drag-end). Color is derived from the project name so
 * the same project always reads the same hue on the grid.
 */
export function DeepWorkCreator({ draft, onChange, disabled }: DeepWorkCreatorProps) {
  const color = blockColor(draft.project || "block")

  return (
    <div className="rounded-lg border border-border bg-bg-panel">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Layers className="h-3.5 w-3.5 shrink-0 text-accent" />
        <span className="label">deep-work block</span>
      </div>

      <div className="space-y-2 p-3">
        <div className="flex flex-wrap gap-2">
          <input
            list="block-projects"
            value={draft.project}
            onChange={(e) => onChange({ ...draft, project: e.target.value })}
            placeholder="project"
            className="min-w-0 flex-1 rounded-md border border-border bg-bg px-2 py-1.5 text-sm text-text placeholder:text-text-label focus:border-accent focus:outline-none"
          />
          <datalist id="block-projects">
            {BLOCK_PROJECTS.map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
          <select
            value={draft.duration_min}
            onChange={(e) => onChange({ ...draft, duration_min: Number(e.target.value) })}
            className="rounded-md border border-border bg-bg px-2 py-1.5 text-sm text-text focus:border-accent focus:outline-none"
            aria-label="duration"
          >
            {DURATIONS.map((m) => (
              <option key={m} value={m}>
                {formatDuration(m)}
              </option>
            ))}
          </select>
        </div>
        <input
          value={draft.title ?? ""}
          onChange={(e) => onChange({ ...draft, title: e.target.value })}
          placeholder="title (optional)"
          className="w-full rounded-md border border-border bg-bg px-2 py-1.5 text-sm text-text placeholder:text-text-label focus:border-accent focus:outline-none"
        />

        <BlockChip draft={draft} color={color} disabled={disabled || !draft.project.trim()} />
        <p className="text-[11px] leading-snug text-text-label">
          drag the chip onto a day to reserve the block.
        </p>
      </div>
    </div>
  )
}

function BlockChip({
  draft,
  color,
  disabled,
}: {
  draft: BlockDraft
  color: string
  disabled?: boolean
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: "newblock",
    disabled,
  })
  return (
    <div
      ref={setNodeRef}
      style={{ borderColor: color, backgroundColor: `${color}1a` }}
      className={cnChip(isDragging, disabled)}
    >
      <button
        type="button"
        className="shrink-0 cursor-grab text-text-disabled hover:text-text-secondary active:cursor-grabbing disabled:cursor-not-allowed"
        disabled={disabled}
        {...attributes}
        {...listeners}
        aria-label="drag new deep-work block"
      >
        <GripVertical className="h-3.5 w-3.5" />
      </button>
      <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />
      <span className="min-w-0 flex-1 truncate text-xs font-medium text-text">
        {draft.project.trim() || "set a project…"}
        {draft.title?.trim() ? ` — ${draft.title.trim()}` : ""}
      </span>
      <span className="shrink-0 font-mono text-[10px] text-text-secondary">
        {formatDuration(draft.duration_min)}
      </span>
    </div>
  )
}

function cnChip(isDragging: boolean, disabled?: boolean): string {
  return [
    "flex items-center gap-1.5 rounded-md border px-2 py-1.5",
    isDragging ? "opacity-40" : "",
    disabled ? "opacity-50" : "",
  ]
    .filter(Boolean)
    .join(" ")
}
