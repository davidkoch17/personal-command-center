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
import { ChevronLeft, ChevronRight } from "lucide-react"
import { api } from "@/lib/api"
import { Skeleton } from "@/components/ui/skeleton"
import { useCalendar } from "@/hooks/useCalendar"
import { DailyPrioritiesPanel } from "@/components/home/DailyPrioritiesPanel"
import { UnifiedDeadlines } from "@/components/planner/UnifiedDeadlines"
import { PlanWeekGrid, isBlockDragId, blockIdFromDrag } from "@/components/planner/PlanWeekGrid"
import { PlanTaskPool } from "@/components/planner/PlanTaskPool"
import { BusyTaskBar } from "@/components/planner/BusyTaskBar"
import { DeepWorkCreator, type BlockDraft } from "@/components/planner/DeepWorkCreator"
import { MonthView } from "@/components/planner/MonthView"
import { WeekStatsDropdown } from "@/components/planner/WeekStatsDropdown"
import { AIAssistantPanel } from "@/components/planner/AIAssistantPanel"
import { cn } from "@/lib/utils"
import {
  DAY_KEYS,
  dayKeyOf,
  blockColor,
  formatDuration,
  getAllAssignedIds,
  getCurrentIsoWeek,
  isPastWeek,
  nextWeek,
  prevWeek,
  type Assignment,
  type DayKey,
  type DeepWorkBlock,
  type PoolResponse,
  type PoolTask,
  type WeekData,
  type WeekResponse,
} from "@/lib/planner"

type Tab = "week" | "month"

const DEFAULT_BLOCK: BlockDraft = { project: "", title: "", duration_min: 90 }

/**
 * Plan (v2 Page 2) — one surface merging Planner + Tasks + Calendar + Daily
 * Priorities. The week grid is the spine: tasks from the pool and deep-work
 * blocks drop onto days, calendar events overlay as a non-draggable layer. A
 * Today strip carries daily priorities + unified hard-deadline display; a
 * busy-task bar lists quick grabs; a month tab gives the longer horizon.
 */
export function Plan() {
  const qc = useQueryClient()
  const [isoWeek, setIsoWeek] = useState<string>(getCurrentIsoWeek())
  const [tab, setTab] = useState<Tab>("week")
  const [draftWeek, setDraftWeek] = useState<WeekData | null>(null)
  const [isDirty, setIsDirty] = useState(false)
  const [aiOpen, setAiOpen] = useState(false)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [blockDraft, setBlockDraft] = useState<BlockDraft>(DEFAULT_BLOCK)

  const readOnly = isPastWeek(isoWeek)
  const isCurrent = isoWeek === getCurrentIsoWeek()

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
  // Two months of events for the month tab's overlay (week tab uses the
  // server-computed per-day overlay in weekData.calendar).
  const { data: calData } = useCalendar(62)

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

  // --- Task assignment editing ----------------------------------------------
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
      if ((DAY_KEYS as readonly string[]).includes(targetContainer)) {
        const dayKey = targetContainer as DayKey
        next[dayKey] = [...(next[dayKey] ?? []), buildEntry(taskId, next[dayKey]?.length ?? 0)]
      }
      return next
    })
    setIsDirty(true)
  }

  function removeTask(taskId: string) {
    moveTask(taskId, "pool")
  }

  // --- Deep-work block editing ----------------------------------------------
  function createBlock(day: DayKey) {
    const project = blockDraft.project.trim()
    if (!project) return
    const block: DeepWorkBlock = {
      id: crypto.randomUUID(),
      project,
      title: blockDraft.title?.trim() || undefined,
      duration_min: blockDraft.duration_min,
      color: blockColor(project),
    }
    setDraftWeek((prev) => {
      if (!prev) return prev
      const blocks = { ...(prev.blocks ?? {}) }
      blocks[day] = [...(blocks[day] ?? []), block]
      return { ...prev, blocks }
    })
    setIsDirty(true)
  }

  function moveBlock(blockId: string, day: DayKey) {
    setDraftWeek((prev) => {
      if (!prev) return prev
      const blocks = { ...(prev.blocks ?? {}) }
      let moving: DeepWorkBlock | undefined
      for (const k of DAY_KEYS) {
        const list = blocks[k] ?? []
        const found = list.find((b) => b.id === blockId)
        if (found) {
          moving = found
          blocks[k] = list.filter((b) => b.id !== blockId)
        }
      }
      if (moving) blocks[day] = [...(blocks[day] ?? []), moving]
      return { ...prev, blocks }
    })
    setIsDirty(true)
  }

  function removeBlock(day: DayKey, blockId: string) {
    setDraftWeek((prev) => {
      if (!prev) return prev
      const blocks = { ...(prev.blocks ?? {}) }
      blocks[day] = (blocks[day] ?? []).filter((b) => b.id !== blockId)
      return { ...prev, blocks }
    })
    setIsDirty(true)
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
    const activeId = active.id as string
    const overId = over.id as string
    const overIsDay = (DAY_KEYS as readonly string[]).includes(overId)

    if (activeId === "newblock") {
      if (overIsDay) createBlock(overId as DayKey)
      return
    }
    if (isBlockDragId(activeId)) {
      const blockId = blockIdFromDrag(activeId)
      if (overIsDay) moveBlock(blockId, overId as DayKey)
      // dropped on the pool → leave it where it was (blocks don't live in pool)
      return
    }
    moveTask(activeId, overId)
  }

  // --- Warn on leave when dirty + Ctrl+S + autosave -------------------------
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

  useEffect(() => {
    if (!isDirty || readOnly) return
    const t = window.setTimeout(() => saveMutation.mutate(), 2500)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDirty, draftWeek, readOnly])

  // Close transient UI when navigating weeks.
  useEffect(() => {
    setAiOpen(false)
  }, [isoWeek])

  const assignedIds = useMemo(
    () => new Set(getAllAssignedIds(draftWeek)),
    [draftWeek],
  )

  if (!draftWeek) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight">plan</h1>
        <Skeleton className="h-10" />
        <Skeleton className="h-[60vh]" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Top bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">plan</h1>
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
          {isCurrent && <span className="text-xs uppercase tracking-wider text-accent">current</span>}
          {readOnly && (
            <span className="text-xs uppercase tracking-wider text-text-label">read-only</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* Tab switcher */}
          <div className="flex items-center rounded-md border border-border p-0.5">
            {(["week", "month"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  "rounded-sm px-2.5 py-1 text-xs font-medium capitalize transition-colors",
                  tab === t ? "bg-accent text-bg" : "text-text-secondary hover:text-text",
                )}
              >
                {t}
              </button>
            ))}
          </div>
          {tab === "week" && !readOnly && (
            <button
              onClick={() => setAiOpen((o) => !o)}
              className="text-sm text-text-secondary hover:text-text"
            >
              AI Assistant
            </button>
          )}
          {isDirty && !readOnly && (
            <span className="h-2 w-2 animate-pulse rounded-full bg-warning" title="unsaved changes" />
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

      {/* A. Today strip — daily priorities + unified hard deadlines */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <DailyPrioritiesPanel />
        <UnifiedDeadlines />
      </div>

      {tab === "month" ? (
        <MonthView
          isoWeek={isoWeek}
          events={calData?.events ?? []}
          onPickWeek={(wk) => {
            setIsoWeek(wk)
            setTab("week")
          }}
        />
      ) : (
        <>
          <WeekStatsDropdown stats={weekData?.stats} />

          <DndContext
            sensors={sensors}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
            onDragCancel={() => setActiveId(null)}
          >
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[60%_40%]">
              {/* B. Week grid (spine) */}
              <PlanWeekGrid
                week={draftWeek}
                calendar={weekData?.calendar ?? {}}
                isoWeek={isoWeek}
                readOnly={readOnly}
                openIds={openIds}
                poolById={poolById}
                onToggle={(taskId) => toggleMutation.mutate(taskId)}
                onRemoveTask={removeTask}
                onRemoveBlock={removeBlock}
              />

              {/* Right rail: AI assistant OR (block creator + task pool) */}
              {aiOpen && !readOnly ? (
                <AIAssistantPanel
                  isoWeek={isoWeek}
                  onClose={() => setAiOpen(false)}
                  onApplyRecommendation={(taskId, day) => moveTask(taskId, day)}
                />
              ) : (
                <div className="space-y-4">
                  {!readOnly && (
                    <DeepWorkCreator draft={blockDraft} onChange={setBlockDraft} />
                  )}
                  <PlanTaskPool
                    tasks={poolData?.pool ?? []}
                    assignedTaskIds={assignedIds}
                    readOnly={readOnly}
                    onToggle={(taskId) => toggleMutation.mutate(taskId)}
                  />
                </div>
              )}
            </div>

            <DragOverlay>{activeId ? <DragPreview activeId={activeId} draftWeek={draftWeek} poolById={poolById} blockDraft={blockDraft} /> : null}</DragOverlay>
          </DndContext>

          {/* D. Busy-task bar */}
          <BusyTaskBar
            tasks={poolData?.pool ?? []}
            assignedTaskIds={assignedIds}
            readOnly={readOnly || !isCurrent}
            onStart={(taskId) => moveTask(taskId, dayKeyOf(new Date()))}
          />
        </>
      )}
    </div>
  )
}

/** What rides under the cursor while dragging: a task, an existing block, or a new block. */
function DragPreview({
  activeId,
  draftWeek,
  poolById,
  blockDraft,
}: {
  activeId: string
  draftWeek: WeekData
  poolById: Map<string, PoolTask>
  blockDraft: BlockDraft
}) {
  if (activeId === "newblock") {
    const color = blockColor(blockDraft.project || "block")
    return (
      <div
        style={{ borderColor: color, backgroundColor: `${color}1f` }}
        className="rounded-md border border-l-4 px-2 py-1.5 text-xs font-medium text-text shadow-lg"
      >
        {blockDraft.project.trim() || "deep-work block"} · {formatDuration(blockDraft.duration_min)}
      </div>
    )
  }
  if (isBlockDragId(activeId)) {
    const id = blockIdFromDrag(activeId)
    for (const day of DAY_KEYS) {
      const b = (draftWeek.blocks?.[day] ?? []).find((x) => x.id === id)
      if (b) {
        return (
          <div
            style={{ borderColor: b.color, backgroundColor: `${b.color}1f` }}
            className="rounded-md border border-l-4 px-2 py-1.5 text-xs font-medium text-text shadow-lg"
          >
            {b.project} · {formatDuration(b.duration_min)}
          </div>
        )
      }
    }
  }
  const text = poolById.get(activeId)?.text ?? findAssignedText(draftWeek, activeId)
  return (
    <div className="rounded-md border border-accent bg-bg-panel px-2 py-1.5 text-xs text-text shadow-lg">
      {text ?? "task"}
    </div>
  )
}

function findAssignedText(week: WeekData, taskId: string): string | undefined {
  for (const day of DAY_KEYS) {
    const found = (week[day] ?? []).find((e) => e.task_id === taskId)
    if (found) return found.text
  }
  return undefined
}
