import { useMemo, type ReactNode } from "react"
import { Link } from "react-router-dom"
import { ArrowRight } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Tag } from "@/components/ui/tag"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { DueTag, daysUntil } from "@/components/todos/due"
import { useTodos, useUpdateTodo, type Todo } from "@/hooks/useTodos"
import { useNetworthSnapshot } from "@/hooks/useNetworth"
import { useCashflowNeedsReview } from "@/hooks/useCashflow"
import { cn, formatCurrency } from "@/lib/utils"

/** How far ahead "coming up" looks. */
const HORIZON_DAYS = 14

function greeting(now: Date): string {
  const h = now.getHours()
  if (h < 12) return "Good morning, David"
  if (h < 18) return "Good afternoon, David"
  return "Good evening, David"
}

/** One headline number that links to the page it summarises. */
function Kpi({
  label,
  value,
  sub,
  to,
  tone = "default",
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  to: string
  tone?: "default" | "danger" | "warning"
}) {
  return (
    <Link to={to} className="panel panel-hover group block transition-colors">
      <div className="label mb-2 flex items-center justify-between">
        {label}
        <ArrowRight className="h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
      </div>
      <div
        className={cn(
          "font-mono text-2xl font-semibold text-text",
          tone === "danger" && "text-danger",
          tone === "warning" && "text-warning",
        )}
      >
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-text-secondary">{sub}</div>}
    </Link>
  )
}

/** Compact to-do row with a done-dot, title, area and due pill. */
function TodoRow({ task }: { task: Todo }) {
  const update = useUpdateTodo()
  const subs = task.subtasks ?? []
  const doneCount = subs.filter((s) => s.done).length
  return (
    <li className="flex items-start gap-3 py-2.5">
      <button
        type="button"
        title="mark done"
        aria-label="mark done"
        disabled={update.isPending}
        onClick={() => update.mutate({ id: task.id, fields: { status: "done" } })}
        className="mt-1 h-3.5 w-3.5 shrink-0 rounded-full border border-text-label transition-colors hover:border-accent hover:bg-accent-soft"
      />
      <div className="min-w-0 flex-1">
        <div className="text-sm text-text">{task.title}</div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          {task.area && <Tag>{task.area}</Tag>}
          {task.status === "waiting" && <Tag variant="warning">waiting</Tag>}
          <DueTag due={task.due} done={false} />
          {subs.length > 0 && (
            <span className="font-mono text-xs text-text-secondary">
              {doneCount}/{subs.length}
            </span>
          )}
        </div>
      </div>
    </li>
  )
}

function TodoList({ tasks, empty }: { tasks: Todo[]; empty: string }) {
  if (tasks.length === 0) return <EmptyState message={empty} />
  return (
    <ul className="divide-y divide-border">
      {tasks.map((t) => (
        <TodoRow key={t.id} task={t} />
      ))}
    </ul>
  )
}

/**
 * Today — the start page. One calm overview of what needs attention: to-dos
 * that are overdue or due soon, what's in progress, net worth this month and
 * cash-flow entries waiting for review. Every block links to its full page.
 */
export function Today() {
  const todos = useTodos()
  const networth = useNetworthSnapshot("1M")
  const review = useCashflowNeedsReview()
  const now = new Date()

  const { dueSoon, withinHorizon, inProgress, openCount, overdueCount } = useMemo(() => {
    const open = (todos.data?.tasks ?? []).filter((t) => t.status !== "done")
    const dated = open
      .filter((t) => t.due && daysUntil(t.due) <= HORIZON_DAYS)
      .sort((a, b) => (a.due ?? "").localeCompare(b.due ?? ""))
    // Nothing inside the horizon → still show the next few dated tasks so the
    // panel is never empty while deadlines exist.
    const upcoming =
      dated.length > 0
        ? dated
        : open
            .filter((t) => t.due)
            .sort((a, b) => (a.due ?? "").localeCompare(b.due ?? ""))
            .slice(0, 3)
    const datedIds = new Set(upcoming.map((t) => t.id))
    return {
      dueSoon: upcoming,
      withinHorizon: dated.length > 0,
      inProgress: open
        .filter((t) => t.status === "in_progress" && !datedIds.has(t.id))
        .sort((a, b) => (a.priority ?? 99) - (b.priority ?? 99)),
      openCount: open.length,
      overdueCount: dated.filter((t) => daysUntil(t.due!) < 0).length,
    }
  }, [todos.data])

  const nw = networth.data
  const delta = nw?.delta_this_month ?? null
  const reviewCount = review.data?.count ?? 0

  return (
    <div className="space-y-8">
      <div>
        <h1 className="page-title normal-case">{greeting(now)}</h1>
        <p className="mt-1 text-sm text-text-secondary">
          {now.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {networth.isLoading ? (
          <Skeleton className="h-[104px]" />
        ) : (
          <Kpi
            label="net worth"
            to="/networth"
            value={nw ? formatCurrency(nw.breakdown.total) : "—"}
            sub={
              delta !== null ? (
                <span className={delta >= 0 ? "text-success" : "text-danger"}>
                  {delta >= 0 ? "+" : "−"}
                  {formatCurrency(Math.abs(delta))} this month
                </span>
              ) : undefined
            }
          />
        )}
        <Kpi
          label="open to-dos"
          to="/todos"
          value={todos.isLoading ? "…" : openCount}
          tone={overdueCount > 0 ? "danger" : "default"}
          sub={overdueCount > 0 ? `${overdueCount} overdue` : "nothing overdue"}
        />
        <Kpi
          label="to review"
          to="/cashflow"
          value={review.isLoading ? "…" : reviewCount}
          tone={reviewCount > 0 ? "warning" : "default"}
          sub={reviewCount > 0 ? "cash-flow entries need a category" : "ledger is clean"}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel
          title={withinHorizon ? "due soon" : "next deadlines"}
          statusDotColor={overdueCount > 0 ? "danger" : withinHorizon ? "warning" : "muted"}
          meta={withinHorizon ? `next ${HORIZON_DAYS} days` : `nothing in the next ${HORIZON_DAYS} days`}
        >
          {todos.isLoading ? (
            <Skeleton className="h-24" />
          ) : (
            <TodoList tasks={dueSoon} empty={`nothing due in the next ${HORIZON_DAYS} days`} />
          )}
        </Panel>
        <Panel title="in progress" statusDotColor="accent" meta={<Link to="/todos" className="hover:text-text">all to-dos →</Link>}>
          {todos.isLoading ? (
            <Skeleton className="h-24" />
          ) : (
            <TodoList tasks={inProgress} empty="nothing in progress" />
          )}
        </Panel>
      </div>
    </div>
  )
}
