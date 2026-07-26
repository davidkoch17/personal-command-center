import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { NumberDisplay } from "@/components/ui/number-display"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { IncomeExpenseBar } from "@/components/charts/finance-charts"
import {
  useCashflowMonths,
  useCashflowSummary,
  useCashflowTrend,
  useSetCashflowGoal,
  type CashflowGoalProgress,
} from "@/hooks/useCashflow"
import { MonthPicker } from "./month-picker"
import { cn, formatCurrency } from "@/lib/utils"

export function OverviewTab() {
  const monthsQ = useCashflowMonths()
  const months = monthsQ.data?.months ?? []
  const [selected, setSelected] = useState<string | null>(null)
  const month = selected ?? (months.length ? months[months.length - 1] : null)

  const summary = useCashflowSummary(month)
  const trend = useCashflowTrend(12)

  return (
    <div className="space-y-4">
      <MonthPicker months={months} month={month} onChange={setSelected} />

      {monthsQ.isLoading || summary.isLoading ? (
        <Skeleton className="h-96" />
      ) : !summary.data ? (
        <Panel title="overview" statusDotColor="muted">
          <p className="text-sm text-text-label">
            no data yet — hand me a bank/card statement, receipt, or screenshot and I'll add it to the ledger.
          </p>
        </Panel>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Panel title="income" statusDotColor="success" className="!py-3">
              <NumberDisplay value={summary.data.income_total} format="currency" emphasized />
            </Panel>
            <Panel title="expenses" statusDotColor="danger" className="!py-3">
              <NumberDisplay value={summary.data.expenses_total} format="currency" emphasized />
            </Panel>
            <Panel title="net" statusDotColor={summary.data.net >= 0 ? "success" : "danger"} className="!py-3">
              <NumberDisplay value={summary.data.net} format="currency" emphasized signed />
            </Panel>
            <Panel title="savings rate" statusDotColor="accent" className="!py-3">
              <NumberDisplay
                value={summary.data.savings_rate != null ? summary.data.savings_rate * 100 : null}
                format="percent"
                emphasized
                signed
              />
            </Panel>
          </div>

          <GoalPanel goal={summary.data.goal} />

          <Panel title="income vs expenses" meta="last 12 months" statusDotColor="accent">
            {trend.isLoading ? <Skeleton className="h-64" /> : <IncomeExpenseBar data={trend.data?.trend ?? []} />}
          </Panel>
        </>
      )}
    </div>
  )
}

function GoalPanel({ goal }: { goal: CashflowGoalProgress }) {
  const setGoal = useSetCashflowGoal()
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(goal.goal != null ? String(goal.goal) : "")

  function save() {
    const num = parseFloat(value)
    setGoal.mutate(Number.isFinite(num) ? num : null, { onSuccess: () => setEditing(false) })
  }

  const pct = goal.percent_of_goal ?? 0
  const statusColor = goal.goal == null ? "muted" : goal.on_track ? "success" : "warning"

  return (
    <Panel title="monthly savings goal" statusDotColor={statusColor}>
      {editing ? (
        <div className="flex items-center gap-2">
          <Input
            mono
            className="h-8 w-32"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="e.g. 1000"
          />
          <Button size="sm" onClick={save} disabled={setGoal.isPending}>
            save
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>
            cancel
          </Button>
        </div>
      ) : goal.goal == null ? (
        <div className="flex items-center justify-between">
          <p className="text-sm text-text-label">no savings goal set yet.</p>
          <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
            set goal
          </Button>
        </div>
      ) : (
        <div className="space-y-2.5">
          <div className="flex items-center justify-between">
            <NumberDisplay value={goal.actual_savings} format="currency" emphasized className="text-2xl" />
            <button onClick={() => setEditing(true)} className="text-xs text-text-label hover:text-accent">
              target {formatCurrency(goal.goal)} · edit
            </button>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-bg-muted">
            <div
              className={cn("h-full rounded-full transition-[width]", goal.on_track ? "bg-success" : "bg-warning")}
              style={{ width: `${Math.min(100, pct)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-text-label">
            <span>{pct}% of goal</span>
            <span>{goal.on_track ? "on track" : "behind goal"}</span>
          </div>
        </div>
      )}
    </Panel>
  )
}
