import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
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
import {
  useMoneyAvailableMonths,
  useMoneyReport,
  type MonthlyReportCategory,
} from "@/hooks/useFinance"
import { MonthPicker } from "./month-picker"
import { ReviewQueue } from "./review-queue"
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

      <ReviewQueue />

      {monthsQ.isLoading || summary.isLoading ? (
        <Skeleton className="h-96" />
      ) : !summary.data ? (
        <Panel title="overview" statusDotColor="muted">
          <EmptyState message="no data yet — hand me a bank/card statement, receipt, or screenshot and I'll add it to the ledger." />
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

          {/* Monthly P&L summary — moved here from the Portfolio pillar. */}
          <MonthlyPnlPanel />

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
          <EmptyState message="no savings goal set yet." />
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
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-border">
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

// One accent hue family (blue/sky tints) — no categorical "rainbow".
const CAT_COLOR: Record<string, string> = {
  Rent: "bg-blue-600",
  Shopping: "bg-blue-800",
  Restaurants: "bg-sky-400",
  Transport: "bg-blue-500",
  Travel: "bg-sky-500",
  Entertainment: "bg-sky-700",
  Groceries: "bg-blue-400",
  Subscriptions: "bg-blue-300",
  Utilities: "bg-sky-300",
  Health: "bg-sky-600",
}

function CategoryBar({ cat, max }: { cat: MonthlyReportCategory; max: number }) {
  const pct = max > 0 ? Math.round((cat.amount / max) * 100) : 0
  const color = CAT_COLOR[cat.category] ?? "bg-text-label"
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-24 shrink-0 text-text-secondary truncate">{cat.category}</span>
      <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-16 text-right tabular-nums text-text-secondary shrink-0">
        {formatCurrency(cat.amount)}
      </span>
    </div>
  )
}

function MonthlyPnlPanel() {
  const months = useMoneyAvailableMonths()
  const allMonths = months.data?.months ?? []
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)

  // Default to latest month once data loads
  const idx = selectedIdx !== null ? selectedIdx : allMonths.length - 1
  const selectedMonth = allMonths[idx] ?? null
  const report = useMoneyReport(selectedMonth)

  const income = report.data?.income.total ?? null
  const expenses = report.data?.expenses.total ?? null
  const net = report.data?.net ?? null
  const rate = report.data?.savings_rate ?? null
  const topCats = (report.data?.expenses.by_category ?? []).slice(0, 5)
  const maxCatAmount = topCats[0]?.amount ?? 0

  const monthLabel = selectedMonth
    ? new Date(selectedMonth + "-01").toLocaleString("en-US", { month: "long", year: "numeric" })
    : undefined

  const canPrev = idx > 0
  const canNext = idx < allMonths.length - 1

  return (
    <Panel title="monthly p&l" statusDotColor="accent">
      {/* Header row: prev / month / next + link */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSelectedIdx(Math.max(0, idx - 1))}
            disabled={!canPrev}
            className="rounded px-1.5 py-0.5 text-xs text-text-label hover:text-text-secondary disabled:opacity-30 transition-colors"
          >
            ←
          </button>
          <span className="font-mono text-xs text-text-secondary tabular-nums min-w-[90px] text-center">
            {monthLabel ?? "—"}
          </span>
          <button
            onClick={() => setSelectedIdx(Math.min(allMonths.length - 1, idx + 1))}
            disabled={!canNext}
            className="rounded px-1.5 py-0.5 text-xs text-text-label hover:text-text-secondary disabled:opacity-30 transition-colors"
          >
            →
          </button>
        </div>
        <a
          href={`/workspace/money?tab=expense+report`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-text-label hover:text-text-secondary transition-colors"
        >
          full report ↗
        </a>
      </div>

      {report.isLoading || months.isLoading ? (
        <Skeleton className="h-32" />
      ) : !report.data ? (
        <EmptyState message="no data — update Finance_Tracker.xlsx to populate." />
      ) : (
        <div className="space-y-4">
          {/* 4 KPI chips */}
          <div className="grid gap-3 sm:grid-cols-4">
            <KpiChip label="income" value={income} format="currency" />
            <KpiChip label="expenses" value={expenses} format="currency" valueClass="text-danger" />
            <KpiChip
              label="net"
              value={net}
              format="currency"
              signed
              valueClass={net != null && net < 0 ? "text-danger" : "text-success"}
            />
            <div className="rounded-sm border border-border bg-bg-panel px-3 py-2">
              <div className="label mb-1">savings rate</div>
              <div className="font-mono text-base font-medium tabular-nums">
                {rate == null ? (
                  <span className="text-text-label">—</span>
                ) : (
                  <span className={rate < 0 ? "text-danger" : rate >= 0.2 ? "text-success" : "text-warning"}>
                    {(rate * 100).toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Income breakdown */}
          {report.data.income.total > 0 && (
            <div className="flex gap-4 text-xs text-text-label">
              {report.data.income.salary > 0 && (
                <span>salary <span className="text-text-secondary font-mono">{formatCurrency(report.data.income.salary)}</span></span>
              )}
              {report.data.income.other > 0 && (
                <span>other income <span className="text-text-secondary font-mono">{formatCurrency(report.data.income.other)}</span></span>
              )}
            </div>
          )}

          {/* Top categories */}
          {topCats.length > 0 && (
            <div className="space-y-1.5">
              <div className="label text-xs text-text-label mb-2">top expenses</div>
              {topCats.map((cat) => (
                <CategoryBar key={cat.category} cat={cat} max={maxCatAmount} />
              ))}
            </div>
          )}
        </div>
      )}
    </Panel>
  )
}

function KpiChip({
  label,
  value,
  format,
  signed,
  valueClass,
}: {
  label: string
  value: number | null
  format: "currency"
  signed?: boolean
  valueClass?: string
}) {
  return (
    <div className="rounded-sm border border-border bg-bg-panel px-3 py-2">
      <div className="label mb-1">{label}</div>
      <div className={`font-mono text-base font-medium tabular-nums ${valueClass ?? ""}`}>
        <NumberDisplay value={value} format={format} signed={signed} />
      </div>
    </div>
  )
}
