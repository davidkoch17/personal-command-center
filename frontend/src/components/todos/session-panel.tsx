import { useState, type ClipboardEvent, type FormEvent } from "react"
import { X } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { TaskCheck } from "@/components/ui/task-check"
import { EmptyState } from "@/components/ui/empty-state"
import { useCreateTodo, useCreateTodos, useUpdateTodo, type Todo } from "@/hooks/useTodos"

/**
 * Working session — a short, focused list of what to get done in one sitting.
 * Session items are ordinary tasks in todos.json with `session: true`, so they
 * also appear in their priority group and sync with chat-Claude. Quick add
 * creates a task (area Other, priority 2) straight onto the list; any task can
 * be pinned here from its card.
 */
export function SessionPanel({ tasks }: { tasks: Todo[] }) {
  const [text, setText] = useState("")
  const create = useCreateTodo()
  const createMany = useCreateTodos()
  const update = useUpdateTodo()

  const session = tasks.filter((t) => t.session)
  const open = session.filter((t) => t.status !== "done")
  const done = session.filter((t) => t.status === "done")

  /** One task per non-empty line (bullets stripped), written in one go. */
  function addTitles(raw: string, onDone?: () => void) {
    const titles = raw
      .split(/\r?\n/)
      .map((l) => l.replace(/^[-*•\s]+/, "").trim())
      .filter(Boolean)
    if (titles.length === 0) return
    const opts = { onSuccess: onDone }
    if (titles.length === 1) create.mutate({ title: titles[0], session: true }, opts)
    else createMany.mutate(titles.map((title) => ({ title, session: true })), opts)
  }

  function add(e: FormEvent) {
    e.preventDefault()
    addTitles(text, () => setText(""))
  }

  // A single-line input would flatten a pasted list, so a multi-line paste
  // is turned into one task per line immediately.
  function onPaste(e: ClipboardEvent<HTMLInputElement>) {
    const pasted = e.clipboardData.getData("text")
    if (!/\r?\n/.test(pasted.trim())) return
    e.preventDefault()
    addTitles(pasted)
  }

  function clearDone() {
    done.forEach((t) => update.mutate({ id: t.id, fields: { session: false } }))
  }

  return (
    <Panel
      title="working session"
      statusDotColor={open.length ? "accent" : "muted"}
      meta={session.length ? `${done.length}/${session.length} done` : undefined}
    >
      <form onSubmit={add} className="mb-3 flex gap-2">
        <Input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onPaste={onPaste}
          placeholder="add something for this session and press enter (paste a list for several)"
          aria-label="add to working session"
        />
        <Button type="submit" variant="secondary" disabled={!text.trim() || create.isPending}>
          add
        </Button>
      </form>

      {session.length === 0 ? (
        <EmptyState message="nothing in this session yet — add above, or pin a task with ◎" />
      ) : (
        <ul className="space-y-0.5">
          {[...open, ...done].map((t) => (
            <li key={t.id} className="group flex items-center gap-1">
              <TaskCheck
                className="flex-1"
                checked={t.status === "done"}
                disabled={update.isPending}
                onToggle={() =>
                  update.mutate({
                    id: t.id,
                    fields: { status: t.status === "done" ? "open" : "done" },
                  })
                }
              >
                {t.title}
              </TaskCheck>
              <button
                type="button"
                title="remove from session (keeps the task)"
                aria-label="remove from session"
                onClick={() => update.mutate({ id: t.id, fields: { session: false } })}
                className="rounded-sm p-1 text-text-label opacity-0 transition-opacity hover:text-text group-hover:opacity-100 focus:opacity-100"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {done.length > 0 && (
        <div className="mt-2 flex justify-end">
          <Button variant="ghost" size="sm" onClick={clearDone}>
            clear finished
          </Button>
        </div>
      )}
    </Panel>
  )
}
