import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Tag } from "@/components/ui/tag"
import { NumberDisplay } from "@/components/ui/number-display"
import { AllocationBar } from "@/components/charts/finance-charts"
import {
  useCashflowMonths,
  useCashflowReserve,
  useCashflowSummary,
  useSetReserveBalance,
  type CashflowActualContribution,
  type CashflowReserveStatus,
} from "@/hooks/useCashflow"
import { useSetContributionOverride } from "@/hooks/useFinance"
import { MonthPicker } from "./month-picker"
import { cn, formatCurrency } from "@/lib/utils"
import { toast } from "@/lib/toast-store"

export function ReserveTab() {
  const monthsQ = useCashflowMonths()
  const months = monthsQ.data?.months ?? []
  const [selected, setSelected] = useState<string | null>(null)
  const month = selected ?? (months.length ? months[months.length - 1] : null)

  const reserve = useCashflowReserve(month)
  const summary = useCashflowSummary(month)

  const data = reserve.data
  const reserveFull = (data?.reserve.percent_filled ?? 0) >= 100 && data?.split_recommendation.to_reserve === 0

  return (
    <div className="space-y-4">
      <MonthPicker months={months} month={month} onChange={setSelected} />

      {monthsQ.isLoading || reserve.isLoading ? (
        <Skeleton className="h-96" />
      ) : !data || !month ? (
        <Panel title="reserve & allocation" statusDotColor="muted">
          <p className="text-sm text-text-label">no data for this month.</p>
        </Panel>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <ReserveGauge reserve={data.reserve} month={month} />
            <SplitPanel
              surplus={data.investable_surplus}
              split={data.split_recommendation}
              reserveFull={reserveFull}
            />
          </div>

          <ContributionPanel
            month={data.month}
            contribution={data.actual_contribution}
            toInvest={data.split_recommendation.to_invest}
            delta={data.contribution_vs_recommended}
          />

          {summary.data && <IncomeByTypePanel incomeByType={summary.data.income_by_category} />}
        </>
      )}
    </div>
  )
}

function ReserveGauge({ reserve, month }: { reserve: CashflowReserveStatus; month: string }) {
  const setBalance = useSetReserveBalance()
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(reserve.reserve_balance != null ? String(reserve.reserve_balance) : "")

  const balance = reserve.reserve_balance
  const pct = reserve.percent_filled
  const full = (pct ?? 0) >= 100

  function save() {
    const num = parseFloat(value)
    if (!Number.isFinite(num)) return
    setBalance.mutate(
      { month, value: num },
      { onSuccess: () => setEditing(false), onError: (e) => toast.error("failed to save balance", String(e)) },
    )
  }

  return (
    <Panel
      title="reserve (notgroschen)"
      meta={`target ${formatCurrency(reserve.target)}`}
      statusDotColor={balance == null ? "muted" : full ? "success" : "warning"}
    >
      {editing ? (
        <div className="flex items-center gap-2">
          <Input mono className="h-8 w-32" value={value} onChange={(e) => setValue(e.target.value)} placeholder="e.g. 1800" />
          <Button size="sm" onClick={save} disabled={setBalance.isPending}>
            save
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>
            cancel
          </Button>
        </div>
      ) : balance == null ? (
        <div className="flex items-center justify-between">
          <p className="text-sm text-text-label">no reserve balance recorded yet.</p>
          <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
            record balance
          </Button>
        </div>
      ) : (
        <div className="space-y-2.5">
          <div className="flex items-center justify-between">
            <NumberDisplay value={balance} format="currency" emphasized className="text-2xl" />
            <button onClick={() => setEditing(true)} className="text-xs text-text-label hover:text-accent">
              edit
            </button>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-bg-muted">
            <div
              className={cn("h-full rounded-full transition-[width]", full ? "bg-success" : "bg-accent")}
              style={{ width: `${Math.min(100, pct ?? 0)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-text-label">
            <span>{pct}% filled</span>
            <span>
              {full || !reserve.remaining_to_target ? "fully funded" : `${formatCurrency(reserve.remaining_to_target)} remaining`}
            </span>
          </div>
        </div>
      )}
    </Panel>
  )
}

function SplitPanel({
  surplus,
  split,
  reserveFull,
}: {
  surplus: number
  split: { to_reserve: number; to_invest: number }
  reserveFull: boolean
}) {
  const total = split.to_reserve + split.to_invest
  const reservePct = total > 0 ? Math.round((split.to_reserve / total) * 100) : 0
  const investPct = total > 0 ? 100 - reservePct : 0

  return (
    <Panel title="this month's recommended split" statusDotColor="accent">
      {surplus <= 0 ? (
        <p className="text-sm text-text-label">no surplus this month — nothing to split.</p>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-sm border border-border bg-bg-panel px-3 py-2">
              <div className="label mb-1">→ reserve</div>
              <NumberDisplay value={split.to_reserve} format="currency" emphasized className="text-lg" />
            </div>
            <div className="rounded-sm border border-border bg-bg-panel px-3 py-2">
              <div className="label mb-1">→ investments</div>
              <NumberDisplay value={split.to_invest} format="currency" emphasized className="text-lg" />
            </div>
          </div>
          {total > 0 && (
            <div className="flex h-2 w-full overflow-hidden rounded-full bg-bg-muted">
              {reservePct > 0 && <div className="h-full bg-warning" style={{ width: `${reservePct}%` }} />}
              {investPct > 0 && <div className="h-full bg-accent" style={{ width: `${investPct}%` }} />}
            </div>
          )}
          <p className="text-xs text-text-label">
            {reserveFull
              ? "reserve full → 100% to investments"
              : `${reservePct}% reserve / ${investPct}% investments (70/30 waterfall until the reserve fills)`}
          </p>
        </div>
      )}
    </Panel>
  )
}

function ContributionPanel({
  month,
  contribution,
  toInvest,
  delta,
}: {
  month: string
  contribution: CashflowActualContribution
  toInvest: number
  delta: number | null
}) {
  const setOverride = useSetContributionOverride()
  const [overrideInput, setOverrideInput] = useState("")

  const chartData =
    contribution.value != null
      ? [
          { type: "recommended", value: toInvest },
          { type: "actual", value: contribution.value },
        ]
      : null

  function saveOverride() {
    const parsed = parseFloat(overrideInput)
    if (!Number.isFinite(parsed)) return
    setOverride.mutate(
      { month, value: parsed },
      {
        onSuccess: () => {
          setOverrideInput("")
          toast.success("contribution override saved", month)
        },
        onError: (e) => toast.error("failed to save override", String(e)),
      },
    )
  }

  return (
    <Panel title="actual TR contribution vs recommended" statusDotColor={contribution.reliable ? "accent" : "warning"}>
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-sm border border-border bg-bg-panel px-3 py-2">
            <div className="label mb-1">recommended</div>
            <NumberDisplay value={toInvest} format="currency" emphasized className="text-lg" />
          </div>
          <div className="rounded-sm border border-border bg-bg-panel px-3 py-2">
            <div className="label mb-1 flex items-center gap-1.5">
              actual
              {contribution.source && (
                <Tag variant={contribution.source === "manual_override" ? "warning" : "accent"}>
                  {contribution.source.replace("_", " ")}
                </Tag>
              )}
            </div>
            <NumberDisplay value={contribution.value} format="currency" emphasized className="text-lg" />
          </div>
          <div className="rounded-sm border border-border bg-bg-panel px-3 py-2">
            <div className="label mb-1">delta (actual − recommended)</div>
            <NumberDisplay value={delta} format="currency" signed className="text-lg" />
          </div>
        </div>

        {chartData && <AllocationBar data={chartData} />}

        {contribution.flags.length > 0 && (
          <div className="space-y-1 rounded-sm border border-warning/30 bg-warning/10 px-3 py-2">
            {contribution.flags.map((f, i) => (
              <p key={i} className="text-xs text-text-secondary">
                ⚠ {f}
              </p>
            ))}
          </div>
        )}

        {!contribution.reliable && (
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <div className="label mb-1">manual override (€)</div>
              <Input mono type="number" value={overrideInput} onChange={(e) => setOverrideInput(e.target.value)} placeholder="e.g. 500" />
            </div>
            <Button size="sm" onClick={saveOverride} disabled={!overrideInput.trim() || setOverride.isPending}>
              save
            </Button>
          </div>
        )}

        <p className="text-xs text-text-label">
          depends on the TR statement parser being verified against a real statement — treat "estimated" values as
          best-effort, not fact, until then.
        </p>
      </div>
    </Panel>
  )
}

// Categories that count toward investable surplus (core/config.py
// CASHFLOW_INVESTABLE_INCOME_CATEGORIES). Display-only classification — the
// actual investable_income sum always comes from the backend.
const INVESTABLE_INCOME_CATEGORIES = new Set(["Salary", "Freelance"])

function IncomeByTypePanel({ incomeByType }: { incomeByType: Record<string, number> }) {
  const entries = Object.entries(incomeByType).sort((a, b) => b[1] - a[1])
  const total = entries.reduce((s, [, v]) => s + v, 0)

  return (
    <Panel title="income by category" meta="salary/freelance count toward surplus" statusDotColor="accent">
      {entries.length === 0 ? (
        <p className="text-sm text-text-label">no income recorded this month.</p>
      ) : (
        <div className="space-y-2">
          {entries.map(([category, amount]) => {
            const pct = total > 0 ? (amount / total) * 100 : 0
            const investable = INVESTABLE_INCOME_CATEGORIES.has(category)
            return (
              <div key={category} className="flex items-center gap-2 text-xs">
                <span className="w-28 shrink-0 text-text-secondary">{category}</span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg-muted">
                  <div
                    className={cn("h-full rounded-full", investable ? "bg-accent" : "bg-text-label")}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="w-16 shrink-0 text-right font-mono tabular-nums text-text-secondary">
                  {formatCurrency(amount)}
                </span>
                <Tag variant={investable ? "accent" : "muted"} className="shrink-0">
                  {investable ? "surplus" : "pass-through"}
                </Tag>
              </div>
            )
          })}
        </div>
      )}
    </Panel>
  )
}
