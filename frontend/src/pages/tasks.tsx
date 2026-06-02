import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { TaskCheck } from "@/components/ui/task-check"
import { StatusDot } from "@/components/ui/status-dot"
import { Skeleton } from "@/components/ui/skeleton"
import { ErrorState } from "@/components/ui/error-state"
import {
  TASK_SECTIONS,
  useAddTask,
  useTasks,
  useToggleTask,
  type TasksBySection,
} from "@/hooks/useTasks"
import type { Task } from "@/lib/types"
import { toast } from "@/lib/toast-store"

export function Tasks() {
  const { data, isLoading, isError, refetch } = useTasks()

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">tasks</h1>

      {isError && (
        <ErrorState message="could not load tasks. is the backend running on :8000?" onRetry={() => refetch()} />
      )}

      {isLoading && (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      )}

      {data && (
        <div className="grid gap-4 md:grid-cols-2">
          {TASK_SECTIONS.filter((s) => s in data).map((section) => (
            <TaskSection
              key={section}
              section={section}
              tasks={(data as TasksBySection)[section] ?? []}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function TaskSection({ section, tasks }: { section: string; tasks: Task[] }) {
  const toggle = useToggleTask()
  const add = useAddTask()
  const [draft, setDraft] = useState("")

  // Preview sections (e.g. "Next week") hold plain dated bullets, not
  // toggleable checkboxes — render them read-only and hide the add box.
  const isPreview = tasks.length > 0 && tasks.every((t) => t.is_task === false)
  const openCount = tasks.filter((t) => !t.checked).length

  function submit() {
    const text = draft.trim()
    if (!text) return
    add.mutate(
      { section, text },
      {
        onSuccess: () => {
          setDraft("")
          toast.success("task added", section)
        },
        onError: (e) => toast.error("could not add task", String(e)),
      },
    )
  }

  return (
    <Panel
      title={section}
      meta={isPreview ? `${tasks.length} ahead` : `${openCount} open`}
      statusDotColor={!isPreview && openCount > 0 ? "accent" : "muted"}
    >
      {!isPreview && (
        <div className="mb-3 flex gap-2">
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder={`add to ${section.toLowerCase()}...`}
          />
          <Button
            size="md"
            onClick={submit}
            disabled={!draft.trim() || add.isPending}
          >
            add
          </Button>
        </div>
      )}

      <div className="space-y-0.5">
        {tasks.length === 0 ? (
          <p className="px-1.5 text-sm text-text-label">nothing here</p>
        ) : (
          tasks.map((t) =>
            t.is_task === false ? (
              <div key={t.line_index} className="flex items-start gap-2 px-1.5 py-1 text-sm">
                <StatusDot color="muted" />
                <span className="text-text-secondary">{t.text}</span>
              </div>
            ) : (
              <TaskCheck
                key={t.line_index}
                checked={t.checked}
                disabled={toggle.isPending}
                onToggle={() =>
                  toggle.mutate(
                    { section, line_index: t.line_index },
                    {
                      onError: (e) =>
                        toast.error("could not toggle task", String(e)),
                    },
                  )
                }
              >
                {t.text}
              </TaskCheck>
            ),
          )
        )}
      </div>
    </Panel>
  )
}
