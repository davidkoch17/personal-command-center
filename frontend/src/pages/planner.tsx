import { useEffect, useMemo, useRef, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core"
import { ChevronLeft, ChevronRight, X } from "lucide-react"
import { api } from "@/lib/api"
import { Skeleton } from "@/components/ui/skeleton"
import { WeekColumns } from "@/components/planner/WeekColumns"
import { TaskPool } from "@/components/planner/TaskPool"
import { WeekStatsDropdown } from "@/components/planner/WeekStatsDropdown"
import { AIAssistantPanel } from "@/components/planner/AIAssistantPanel"
import { isoDate } from "@/lib/utils"
import {
  DAY_KEYS,
  dayKeyOf,
  getAllAssignedIds,
  getCurrentIsoWeek,
  isPastWeek,
  nextWeek,
  prevWeek,
  type AIRecommendResponse,
  type Assignment,
  type PoolResponse,
  type PoolTask,
  type WeekData,
  type WeekResponse,
} from "@/lib/planner"

const AUTOFILL_COUNT = 5

export function Planner() {
  const qc = useQueryClient()
  const [isoWeek, setIsoWeek] = useState<string>(getCurrentIsoWeek())
  const [draftWeek, setDraftWeek] = useState<WeekData | null>(null)
  const [isDirty, setIsDirty] = useState(false)
  const [aiOpen, setAiOpen] = useState(false)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [autofillBanner, setAutofillBanner] = useState(false)

  const readOnly = isPastWeek(isoWeek)
  const isCurrent = isoWeek === getCurrentIsoWeek()

  // Keep a ref of dirtiness so the server-sync effect can read it without
  // re-subscribing (and clobbering unsaved drag edits on unrelated refetches).
  const isDirtyRef = useRef(isDirty)
  isDirtyRef.current = isDirty

  // --- Queries --------------------------------------------------------------
  const { data: weekData } = useQuery({
    queryKey: ["planner-week", isoWeek],
    queryFn: () => api.get<WeekResponse>(`/api/planner/week/${isoWeek}`),
  })
  const { data: poolData } = useQuery({
    queryKey: ["planner-pool"],
    queryFn: () => api.get<PoolResponse>("/api/planner/pool"),
  })

  // Adopt server week on navigation or when there are no unsaved edits.
  useEffect(() => {
    if (!weekData?.week) return
    setDraftWeek((prev) => {
      if (!prev) return weekData.week
      if (prev.iso_week !== weekData.week.iso_week) return weekData.week
      if (!isDirtyRef.current) return weekData.week
      return prev
    })
  }, [weekData])

  const poolById = useMemo(() => {
    const m = new Map<string, PoolTask>()
    for (const t of poolData?.pool ?? []) m.set(t.id, t)
    return m
  }, [poolData])

  const openIds = useMemo(() => new Set(poolData?.open_ids ?? []), [poolData])

  // --- Mutations ------------------------------------------------------------
  const saveMutation = useMutation({
    mutationFn: () => api.post(`/api/planner/week/${isoWeek}`, { week: draftWeek }),
    onSuccess: () => {
      setIsDirty(false)
      qc.invalidateQueries({ queryKey: ["planner-week", isoWeek] })
    },
  })

  const toggleMutation = useMutation({
    mutationFn: (taskId: string) => api.post("/api/planner/toggle", { task_id: taskId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["planner-pool"] })
      qc.invalidateQueries({ queryKey: ["planner-week", isoWeek] })
    },
  })

  // --- Assignment editing ---------------------------------------------------
  /** Build a day-assignment entry, preserving cached text/source for the task. */
  function buildEntry(taskId: string, order: number): Assignment {
    if (draftWeek) {
      for (const day of DAY_KEYS) {
        const found = (draftWeek[day] ?? []).find((e) => e.task_id === taskId)
        if (found) return { ...found, order }
      }
    }
    const pt = poolById.get(taskId)
    return { task_id: taskId, order, text: pt?.text, source_label: pt?.source_label }
  }

  function moveTask(taskId: string, targetContainer: string) {
    setDraftWeek((prev) => {
      if (!prev) return prev
      const next: WeekData = { ...prev }
      for (const day of DAY_KEYS) {
        next[day] = (next[day] ?? []).filter((e) => e.task_id !== taskId)
      }
      if (targetContainer !== "pool" && (DAY_KEYS as readonly string[]).includes(targetContainer)) {
        const dayKey = targetContainer as (typeof DAY_KEYS)[number]
        next[dayKey] = [...(next[dayKey] ?? []), buildEntry(taskId, next[dayKey]?.length ?? 0)]
      }
      return next
    })
    setIsDirty(true)
  }

  function removeTask(taskId: string) {
    moveTask(taskId, "pool")
  }

  // --- Drag and drop --------------------------------------------------------
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { delay: 100, tolerance: 5 } }),
  )

  function handleDragStart(event: DragStartEvent) {
    setActiveId(event.active.id as string)
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveId(null)
    const { active, over } = event
    if (!over || !draftWeek || readOnly) return
    moveTask(active.id as string, over.id as string)
  }

  // --- Warn on leave when dirty ---------------------------------------------
  useEffect(() => {
    if (!isDirty) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ""
      return ""
    }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [isDirty])

  // --- Cmd/Ctrl+S to save ---------------------------------------------------
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault()
        if (isDirty && !readOnly) saveMutation.mutate()
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDirty, readOnly])

  // --- Auto-save debounce ---------------------------------------------------
  useEffect(() => {
    if (!isDirty || readOnly) return
    const t = window.setTimeout(() => saveMutation.mutate(), 2500)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDirty, draftWeek, readOnly])

  // --- Today's column auto-fill (replaces Daily Priorities) -----------------
  const autofillTried = useRef(false)
  useEffect(() => {
    if (autofillTried.current) return
    if (!isCurrent || readOnly || !draftWeek || !poolData) return
    const todayKey = dayKeyOf(new Date())
    if ((draftWeek[todayKey] ?? []).length > 0) return
    const guardKey = `planner-autofill-${isoDate()}`
    if (localStorage.getItem(guardKey)) return

    autofillTried.current = true
    localStorage.setItem(guardKey, "1")
    void api
      .post<AIRecommendResponse>(`/api/planner/ai-recommend/${isoWeek}`, {})
      .then((res) => {
        const picks = (res.recommendations ?? [])
          .filter((r) => r.suggested_day !== "later")
          .slice(0, AUTOFILL_COUNT)
        if (picks.length === 0) return
        setDraftWeek((prev) => {
          if (!prev) return prev
          const next: WeekData = { ...prev }
          const existing = next[todayKey] ?? []
          const additions = picks.map((r, i) => {
            const pt = poolById.get(r.task_id)
            return {
              task_id: r.task_id,
              order: existing.length + i,
              text: r.task_text ?? pt?.text,
              source_label: pt?.source_label,
            } as Assignment
          })
          next[todayKey] = [...existing, ...additions]
          return next
        })
        setIsDirty(true)
        setAutofillBanner(true)
      })
      .catch(() => {
        /* best-effort: leave today empty if Claude is unavailable */
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCurrent, readOnly, draftWeek, poolData, isoWeek])

  // Reset transient UI when navigating weeks.
  useEffect(() => {
    setAiOpen(false)
    setAutofillBanner(false)
  }, [isoWeek])

  if (!draftWeek) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight">planner</h1>
        <Skeleton className="h-10" />
        <Skeleton className="h-[60vh]" />
      </div>
    )
  }

  const dragText = activeId
    ? poolById.get(activeId)?.text ?? findAssignedText(draftWeek, activeId)
    : undefined

  return (
    <div className="space-y-4">
      {/* Top bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">planner</h1>
          <button
            onClick={() => setIsoWeek(prevWeek(isoWeek))}
            className="text-text-secondary hover:text-text"
            aria-label="previous week"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <span className="font-mono text-sm text-text-secondary tabular-nums">{isoWeek}</span>
          <button
            onClick={() => setIsoWeek(nextWeek(isoWeek))}
            className="text-text-secondary hover:text-text"
            aria-label="next week"
          >
            <ChevronRight className="h-5 w-5" />
          </button>
          {isCurrent && (
            <span className="text-xs uppercase tracking-wider text-accent">current</span>
          )}
          {readOnly && (
            <span className="text-xs uppercase tracking-wider text-text-label">read-only</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {!readOnly && (
            <button
              onClick={() => setAiOpen((o) => !o)}
              className="text-sm text-text-secondary hover:text-text"
            >
              ai assistant
            </button>
          )}
          {isDirty && !readOnly && (
            <span
              className="h-2 w-2 animate-pulse rounded-full bg-warning"
              title="unsaved changes"
            />
          )}
          {!readOnly && (
            <button
              onClick={() => saveMutation.mutate()}
              disabled={!isDirty || saveMutation.isPending}
              className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-bg hover:bg-accent-dim disabled:bg-text-disabled disabled:text-text-secondary"
            >
              {saveMutation.isPending ? "saving..." : "save"}
            </button>
          )}
        </div>
      </div>

      {/* Auto-fill banner */}
      {autofillBanner && (
        <div className="flex items-center justify-between gap-3 rounded-md border border-accent-dim bg-accent-soft/20 px-3 py-2">
          <span className="text-sm text-text">
            Today's suggestions filled in from Claude. Drag to refine.
          </span>
          <button
            onClick={() => setAutofillBanner(false)}
            aria-label="dismiss"
            className="text-text-secondary hover:text-text"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Stats dropdown */}
      <WeekStatsDropdown stats={weekData?.stats} />

      {/* Main layout */}
      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={() => setActiveId(null)}
      >
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[60%_40%]">
          <WeekColumns
            week={draftWeek}
            calendar={weekData?.calendar ?? {}}
            isoWeek={isoWeek}
            readOnly={readOnly}
            openIds={openIds}
            poolById={poolById}
            onToggle={(taskId) => toggleMutation.mutate(taskId)}
            onRemove={removeTask}
          />
          {aiOpen && !readOnly ? (
            <AIAssistantPanel
              isoWeek={isoWeek}
              onClose={() => setAiOpen(false)}
              onApplyRecommendation={(taskId, day) => moveTask(taskId, day)}
            />
          ) : (
            <TaskPool
              tasks={poolData?.pool ?? []}
              assignedTaskIds={new Set(getAllAssignedIds(draftWeek))}
              readOnly={readOnly}
              onToggle={(taskId) => toggleMutation.mutate(taskId)}
            />
          )}
        </div>

        <DragOverlay>
          {activeId ? (
            <div className="rounded-md border border-accent bg-bg-panel px-2 py-1.5 text-xs text-text shadow-lg">
              {dragText ?? "task"}
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  )
}

/** Look up the cached text of an assigned task across all days. */
function findAssignedText(week: WeekData, taskId: string): string | undefined {
  for (const day of DAY_KEYS) {
    const found = (week[day] ?? []).find((e) => e.task_id === taskId)
    if (found) return found.text
  }
  return undefined
}
