import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { X, AlertTriangle, Sparkles } from "lucide-react"
import { api } from "@/lib/api"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import {
  DAY_KEYS,
  dayLabel,
  type AIRecommendResponse,
  type AIRecommendation,
  type DayKey,
} from "@/lib/planner"

interface AIAssistantPanelProps {
  isoWeek: string
  onClose: () => void
  onApplyRecommendation: (taskId: string, day: string) => void
}

/**
 * Right-side panel that asks Claude where to place open tasks this week. Each
 * card carries a suggested day + rationale with Apply / Skip / a "different day"
 * override. Claude calls are slow (~30-60s) so a skeleton holds the space.
 */
export function AIAssistantPanel({
  isoWeek,
  onClose,
  onApplyRecommendation,
}: AIAssistantPanelProps) {
  const [handled, setHandled] = useState<Record<string, true>>({})
  const [overrides, setOverrides] = useState<Record<string, string>>({})

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["planner-ai", isoWeek],
    queryFn: () => api.post<AIRecommendResponse>(`/api/planner/ai-recommend/${isoWeek}`, {}),
    staleTime: Infinity,
    gcTime: 5 * 60 * 1000,
    retry: false,
  })

  const recs = useMemo(() => data?.recommendations ?? [], [data])
  const pending = recs.filter((r) => !handled[r.task_id])

  function dayFor(r: AIRecommendation): string {
    return overrides[r.task_id] ?? r.suggested_day
  }

  function apply(r: AIRecommendation) {
    onApplyRecommendation(r.task_id, dayFor(r))
    setHandled((h) => ({ ...h, [r.task_id]: true }))
  }

  function applyAll() {
    for (const r of pending) {
      const day = dayFor(r)
      if (day && day !== "later") onApplyRecommendation(r.task_id, day)
    }
    setHandled((h) => {
      const next = { ...h }
      for (const r of pending) next[r.task_id] = true
      return next
    })
  }

  return (
    <div className="flex h-full max-h-[calc(100vh-220px)] flex-col rounded-lg border border-accent-dim bg-bg-panel">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-3 py-2.5">
        <span className="flex items-center gap-2 text-sm font-medium text-text">
          <Sparkles className="h-4 w-4 text-accent" />
          ai assistant — recommendations for this week
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="close assistant"
          className="text-text-secondary hover:text-text"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {isLoading || isFetching ? (
          <>
            <p className="text-sm text-text-secondary">claude is thinking… (~30-60s)</p>
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </>
        ) : isError ? (
          <p className="text-sm text-text-label">could not get recommendations.</p>
        ) : (
          <>
            {data?.warnings && data.warnings.length > 0 && (
              <div className="space-y-1 rounded-md border border-warning/40 bg-warning/10 p-2">
                {data.warnings.map((w, i) => (
                  <p key={i} className="flex items-start gap-1.5 text-xs text-warning">
                    <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                    {w}
                  </p>
                ))}
              </div>
            )}
            {data?.summary && (
              <p className="text-xs italic text-text-secondary">{data.summary}</p>
            )}
            {pending.length === 0 ? (
              <p className="py-2 text-sm text-text-label">
                {recs.length === 0 ? "no recommendations." : "all recommendations handled."}
              </p>
            ) : (
              pending.map((r) => (
                <RecCard
                  key={r.task_id}
                  rec={r}
                  selectedDay={dayFor(r)}
                  onApply={() => apply(r)}
                  onSkip={() => setHandled((h) => ({ ...h, [r.task_id]: true }))}
                  onChangeDay={(day) =>
                    setOverrides((o) => ({ ...o, [r.task_id]: day }))
                  }
                />
              ))
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between gap-2 border-t border-border px-3 py-2.5">
        <button
          type="button"
          onClick={() => {
            setHandled({})
            setOverrides({})
            void refetch()
          }}
          disabled={isFetching}
          className="text-xs text-text-secondary hover:text-text disabled:opacity-50"
        >
          regenerate
        </button>
        <button
          type="button"
          onClick={applyAll}
          disabled={pending.length === 0 || isFetching}
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-bg hover:bg-accent-dim disabled:bg-text-disabled disabled:text-text-secondary"
        >
          apply all
        </button>
      </div>
    </div>
  )
}

function RecCard({
  rec,
  selectedDay,
  onApply,
  onSkip,
  onChangeDay,
}: {
  rec: AIRecommendation
  selectedDay: string
  onApply: () => void
  onSkip: () => void
  onChangeDay: (day: string) => void
}) {
  const isLater = selectedDay === "later"
  return (
    <div className="rounded-md border border-border bg-bg p-2">
      <p className="text-xs leading-snug text-text">{rec.task_text}</p>
      <div className="mt-1.5 flex items-center gap-2">
        <span
          className={cn(
            "rounded-sm px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider",
            isLater
              ? "bg-text-disabled/30 text-text-secondary"
              : "bg-accent-soft text-accent",
          )}
        >
          {isLater ? "later" : dayLabel(selectedDay as DayKey)}
        </span>
        <select
          value={selectedDay}
          onChange={(e) => onChangeDay(e.target.value)}
          className="rounded-sm border border-border bg-bg-panel px-1 py-0.5 text-[10px] text-text-secondary focus:border-accent focus:outline-none"
          aria-label="different day"
        >
          {DAY_KEYS.map((d) => (
            <option key={d} value={d}>
              {dayLabel(d)}
            </option>
          ))}
          <option value="later">later</option>
        </select>
      </div>
      {rec.rationale && (
        <p className="mt-1 text-[11px] italic leading-snug text-text-label">{rec.rationale}</p>
      )}
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={onApply}
          disabled={isLater}
          className="rounded-sm bg-accent px-2 py-0.5 text-[11px] font-medium text-bg hover:bg-accent-dim disabled:bg-text-disabled disabled:text-text-secondary"
        >
          apply
        </button>
        <button
          type="button"
          onClick={onSkip}
          className="rounded-sm border border-border px-2 py-0.5 text-[11px] text-text-secondary hover:text-text"
        >
          skip
        </button>
      </div>
    </div>
  )
}
