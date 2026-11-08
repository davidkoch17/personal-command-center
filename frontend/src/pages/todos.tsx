import { useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { ChevronDown, ChevronRight, Pencil, Plus, Trash2, X } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Tag } from "@/components/ui/tag"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Toggle } from "@/components/ui/toggle"
import { TaskCheck } from "@/components/ui/task-check"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { ErrorState } from "@/components/ui/error-state"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  useCreateTodo,
  useDeleteTodo,
  useTodos,
  useToggleSubtask,
  useUpdateTodo,
  type Todo,
  type TodoFields,
  type TodoStatus,
  type TodoSubtask,
} from "@/hooks/useTodos"
import { cn } from "@/lib/utils"
import { DueTag } from "@/components/todos/due"

const STATUS_LABEL: Record<TodoStatus, string> = {
  open: "open",
  in_progress: "in progress",
  waiting: "waiting",
  done: "done",
}

const STATUS_VARIANT: Record<TodoStatus, "muted" | "accent" | "warning" | "success"> = {
  open: "muted",
  in_progress: "accent",
  waiting: "warning",
  done: "success",
}

type StatusFilter = "all" | TodoStatus

// --- Sorting ------------------------------------------------------------------

/** Sort: by due date ascending (undated last), then title. */
function byDue(a: Todo, b: Todo): number {
  if (a.due && b.due) return a.due.localeCompare(b.due) || a.title.localeCompare(b.title)
  if (a.due) return -1
  if (b.due) return 1
  return a.title.localeCompare(b.title)
}

// --- Task card -------------------------------------------------------------------

function TodoCard({ task, onEdit }: { task: Todo; onEdit: (t: Todo) => void }) {
  const [open, setOpen] = useState(false)
  const update = useUpdateTodo()
  const toggleSub = useToggleSubtask()
  const subs = task.subtasks ?? []
  const doneCount = subs.filter((s) => s.done).length
  const isDone = task.status === "done"

  return (
    <div>
      <div className="flex items-start gap-2 px-2 py-2">
        <button
          type="button"
          title={isDone ? "reopen" : "mark done"}
          aria-label={isDone ? "reopen" : "mark done"}
          disabled={update.isPending}
          onClick={() =>
            update.mutate({ id: task.id, fields: { status: isDone ? "open" : "done" } })
          }
          className={cn(
            "mt-1 h-3.5 w-3.5 shrink-0 rounded-full border transition-colors",
            isDone ? "bg-accent border-accent" : "border-text-label hover:border-accent",
          )}
        />
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex min-w-0 flex-1 items-start gap-1.5 text-left"
        >
          {open ? (
            <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-text-secondary" />
          ) : (
            <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-text-secondary" />
          )}
          <span className="min-w-0 flex-1">
            <span
              className={cn(
                "block text-sm",
                isDone ? "text-text-secondary line-through" : "text-text",
              )}
            >
              {task.title}
            </span>
            <span className="mt-1 flex flex-wrap items-center gap-1.5">
              {task.area && <Tag>{task.area}</Tag>}
              <Tag variant={STATUS_VARIANT[task.status] ?? "muted"}>
                {STATUS_LABEL[task.status] ?? task.status}
              </Tag>
              <DueTag due={task.due} done={isDone} />
              {subs.length > 0 && (
                <span className="font-mono text-xs text-text-secondary">
                  {doneCount}/{subs.length}
                </span>
              )}
            </span>
          </span>
        </button>
        <Button variant="ghost" size="sm" onClick={() => onEdit(task)} aria-label="edit">
          <Pencil className="h-3.5 w-3.5" />
        </Button>
      </div>

      {subs.length > 0 && (
        <div className="mx-2 mb-2 h-1 overflow-hidden rounded-full bg-bg-panel-hover">
          <div
            className="h-full bg-accent transition-[width]"
            style={{ width: `${(doneCount / subs.length) * 100}%` }}
          />
        </div>
      )}

      {open && (
        <div className="mx-2 mb-3 space-y-3 rounded bg-bg px-3 py-3">
          {task.notes ? (
            <p className="whitespace-pre-wrap text-sm text-text-secondary">{task.notes}</p>
          ) : (
            <EmptyState message="no notes" />
          )}
          {subs.length > 0 && (
            <div className="space-y-0.5">
              {subs.map((s, i) => (
                <TaskCheck
                  key={i}
                  checked={s.done}
                  disabled={toggleSub.isPending}
                  onToggle={() => toggleSub.mutate({ id: task.id, index: i, done: !s.done })}
                >
                  <span className="flex items-center gap-2">
                    <span>{s.title}</span>
                    {(s.priority ?? 1) > 1 && (
                      <span className="font-mono text-[10px] text-text-label">p{s.priority}</span>
                    )}
                  </span>
                </TaskCheck>
              ))}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <span className="label">status</span>
            <Toggle
              value={task.status}
              disabled={update.isPending}
              options={(Object.keys(STATUS_LABEL) as TodoStatus[]).map((s) => ({
                value: s,
                label: STATUS_LABEL[s],
              }))}
              onChange={(status) => update.mutate({ id: task.id, fields: { status } })}
            />
          </div>
        </div>
      )}
    </div>
  )
}

// --- Create / edit dialog -------------------------------------------------------

interface Draft {
  title: string
  area: string
  priority: number
  status: TodoStatus
  due: string
  notes: string
  subtasks: TodoSubtask[]
}

function toDraft(task: Todo | null): Draft {
  return {
    title: task?.title ?? "",
    area: task?.area ?? "",
    priority: task?.priority ?? 2,
    status: task?.status ?? "open",
    due: task?.due ?? "",
    notes: task?.notes ?? "",
    subtasks: (task?.subtasks ?? []).map((s) => ({ ...s })),
  }
}

function TodoDialog({
  task,
  areas,
  open,
  onClose,
}: {
  task: Todo | null // null = create
  areas: string[]
  open: boolean
  onClose: () => void
}) {
  const [draft, setDraft] = useState<Draft>(() => toDraft(task))
  const create = useCreateTodo()
  const update = useUpdateTodo()
  const del = useDeleteTodo()
  const busy = create.isPending || update.isPending || del.isPending

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => ({ ...d, [k]: v }))
  const setSub = (i: number, patch: Partial<TodoSubtask>) =>
    set(
      "subtasks",
      draft.subtasks.map((s, j) => (j === i ? { ...s, ...patch } : s)),
    )

  function save() {
    const fields: TodoFields = {
      title: draft.title.trim(),
      area: draft.area.trim(),
      priority: draft.priority,
      status: draft.status,
      due: draft.due || null,
      notes: draft.notes,
      subtasks: draft.subtasks.filter((s) => s.title.trim()),
    }
    const done = { onSuccess: onClose }
    if (task) update.mutate({ id: task.id, fields }, done)
    else create.mutate(fields, done)
  }

  function remove() {
    if (!task) return
    if (!window.confirm(`delete "${task.title}" from todos.json? (mark it done to just hide it)`)) return
    del.mutate(task.id, { onSuccess: onClose })
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{task ? "edit task" : "new task"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <Input
            autoFocus
            placeholder="title"
            value={draft.title}
            onChange={(e) => set("title", e.target.value)}
          />
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className="col-span-2 sm:col-span-1">
              <span className="label">area</span>
              <Input
                list="todo-areas"
                value={draft.area}
                onChange={(e) => set("area", e.target.value)}
              />
              <datalist id="todo-areas">
                {areas.map((a) => (
                  <option key={a} value={a} />
                ))}
              </datalist>
            </div>
            <div>
              <span className="label">priority</span>
              <Input
                type="number"
                min={1}
                mono
                value={draft.priority}
                onChange={(e) => set("priority", Math.max(1, Number(e.target.value) || 1))}
              />
            </div>
            <div>
              <span className="label">status</span>
              <Select value={draft.status} onValueChange={(v) => set("status", v as TodoStatus)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(Object.keys(STATUS_LABEL) as TodoStatus[]).map((s) => (
                    <SelectItem key={s} value={s}>
                      {STATUS_LABEL[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <span className="label">due</span>
              <Input type="date" mono value={draft.due} onChange={(e) => set("due", e.target.value)} />
            </div>
          </div>
          <div>
            <span className="label">notes</span>
            <Textarea value={draft.notes} onChange={(e) => set("notes", e.target.value)} />
            <p className="mt-1 text-xs text-text-label">
              no card numbers, passwords or activation codes — this file syncs via OneDrive.
            </p>
          </div>
          <div className="space-y-1.5">
            <span className="label">subtasks</span>
            {draft.subtasks.map((s, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={s.done}
                  onChange={(e) => setSub(i, { done: e.target.checked })}
                  className="h-4 w-4 accent-[rgb(var(--color-accent))]"
                />
                <Input
                  value={s.title}
                  onChange={(e) => setSub(i, { title: e.target.value })}
                  className="h-8"
                />
                <Input
                  type="number"
                  min={1}
                  mono
                  title="priority"
                  value={s.priority ?? 1}
                  onChange={(e) => setSub(i, { priority: Math.max(1, Number(e.target.value) || 1) })}
                  className="h-8 w-16"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label="remove subtask"
                  onClick={() => set("subtasks", draft.subtasks.filter((_, j) => j !== i))}
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                set("subtasks", [...draft.subtasks, { title: "", done: false, priority: 1 }])
              }
            >
              <Plus className="h-3.5 w-3.5" /> add subtask
            </Button>
          </div>
        </div>
        <DialogFooter className="justify-between">
          {task ? (
            <Button variant="ghost" size="sm" onClick={remove} disabled={busy}>
              <Trash2 className="h-3.5 w-3.5" /> delete
            </Button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onClose} disabled={busy}>
              cancel
            </Button>
            <Button onClick={save} disabled={busy || !draft.title.trim()}>
              save
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// --- Page --------------------------------------------------------------------------

/**
 * To-dos pillar — Personal Admin tasks from the shared `todos.json` in OneDrive
 * (also edited by chat-Claude). Grouped by priority, sorted by due date.
 */
export function Todos() {
  const { data, isLoading, isError, refetch } = useTodos()
  const [params, setParams] = useSearchParams()
  const area = params.get("area") ?? "all"
  const status = (params.get("status") ?? "all") as StatusFilter
  const showDone = params.get("done") === "1"
  const [editing, setEditing] = useState<Todo | null>(null)
  const [creating, setCreating] = useState(false)

  function setParam(key: string, value: string | null) {
    setParams((p) => {
      if (value === null) p.delete(key)
      else p.set(key, value)
      return p
    })
  }

  const tasks = data?.tasks ?? []
  const areas = useMemo(
    () => [...new Set(tasks.map((t) => t.area).filter(Boolean))].sort(),
    [tasks],
  )

  const groups = useMemo(() => {
    const visible = tasks.filter(
      (t) =>
        (area === "all" || t.area === area) &&
        (status === "all" ? showDone || t.status !== "done" : t.status === status),
    )
    const byPrio = new Map<number, Todo[]>()
    for (const t of visible) {
      const p = t.priority ?? 99
      byPrio.set(p, [...(byPrio.get(p) ?? []), t])
    }
    return [...byPrio.entries()]
      .sort(([a], [b]) => a - b)
      .map(([prio, list]) => ({ prio, list: list.sort(byDue) }))
  }, [tasks, area, status, showDone])

  const openCount = tasks.filter((t) => t.status !== "done").length
  const doneCount = tasks.length - openCount

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="page-title">to-dos</h1>
        <Button size="sm" onClick={() => setCreating(true)}>
          <Plus className="h-3.5 w-3.5" /> new task
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="w-44">
          <Select value={area} onValueChange={(v) => setParam("area", v === "all" ? null : v)}>
            <SelectTrigger className="h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">all areas</SelectItem>
              {areas.map((a) => (
                <SelectItem key={a} value={a}>
                  {a}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Toggle<StatusFilter>
          value={status}
          onChange={(v) => setParam("status", v === "all" ? null : v)}
          options={[
            { value: "all", label: "all" },
            { value: "open", label: "open" },
            { value: "in_progress", label: "in progress" },
            { value: "waiting", label: "waiting" },
            { value: "done", label: "done" },
          ]}
        />
        <label className="flex cursor-pointer items-center gap-2 text-xs text-text-secondary">
          <input
            type="checkbox"
            checked={showDone}
            onChange={(e) => setParam("done", e.target.checked ? "1" : null)}
            className="h-3.5 w-3.5 accent-[rgb(var(--color-accent))]"
          />
          show done ({doneCount})
        </label>
      </div>

      {isLoading ? (
        <Skeleton className="h-40" />
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : groups.length === 0 ? (
        <Panel>
          <EmptyState message={openCount === 0 ? "nothing open — all done" : "no tasks match these filters"} />
        </Panel>
      ) : (
        groups.map(({ prio, list }) => (
          <Panel
            key={prio}
            title={`priority ${prio}`}
            statusDotColor={prio === 1 ? "danger" : prio === 2 ? "warning" : "muted"}
            meta={`${list.length} task${list.length === 1 ? "" : "s"}`}
          >
            <div className="-mx-2 divide-y divide-border">
              {list.map((t) => (
                <TodoCard key={t.id} task={t} onEdit={setEditing} />
              ))}
            </div>
          </Panel>
        ))
      )}

      {data && <p className="text-xs text-text-label">last updated {data.updated}</p>}

      {(creating || editing) && (
        <TodoDialog
          key={editing?.id ?? "new"}
          task={editing}
          areas={areas}
          open
          onClose={() => {
            setCreating(false)
            setEditing(null)
          }}
        />
      )}
    </div>
  )
}
