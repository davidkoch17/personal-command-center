import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Tag } from "@/components/ui/tag"
import { NumberDisplay } from "@/components/ui/number-display"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { IncomeExpenseBar, CategoryDonut, CategoryTrendLine, AllocationBar } from "@/components/charts/finance-charts"
import { TaxIntegrationPanels } from "@/components/finance/tax-panel"
import {
  useMoneySnapshot,
  useMoneyCashflow,
  useMoneyCategories,
  useMoneyAvailableMonths,
  useMoneyReport,
  useMoneyAllocation,
  useSetContributionOverride,
  type ActualContribution,
  type AllocationReserveStatus,
  type AllocationSplitRecommendation,
} from "@/hooks/useFinance"
import { useProjects } from "@/hooks/useProjects"
import { useRunSkill, useTaxScenario } from "@/hooks/useSkills"
import { categoryNames, lastCategoryBreakdown } from "@/lib/money"
import { cn, formatCurrency } from "@/lib/utils"
import { toast } from "@/lib/toast-store"

const YEAR_END_CHECKLIST = [
  "gather annual Lohnsteuerbescheinigung",
  "collect deductible receipts (work, BU, PKV)",
  "confirm Werbungskosten above the pauschale",
  "Steuerberater appointment booked",
  "submit by deadline (31 jul, or later with berater)",
]

export function MoneyWorkspace() {
  const cashflow = useMoneyCashflow(12)
  const categories = useMoneyCategories(12)

  return (
    <div className="min-h-screen bg-bg text-text p-6">
      <div className="mx-auto max-w-[1400px] space-y-5">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">money workspace</h1>
          <Link to="/portfolio?tab=overview" className="font-mono text-xs text-text-secondary hover:text-accent">
            ← net worth
          </Link>
        </div>

        <Tabs defaultValue="cashflow">
          <TabsList>
            <TabsTrigger value="cashflow">cash flow</TabsTrigger>
            <TabsTrigger value="allocation">reserve & allocation</TabsTrigger>
            <TabsTrigger value="categories">categories</TabsTrigger>
            <TabsTrigger value="networth">net worth</TabsTrigger>
            <TabsTrigger value="forecast">forecast</TabsTrigger>
            <TabsTrigger value="budget">budget</TabsTrigger>
            <TabsTrigger value="tax">tax</TabsTrigger>
            <TabsTrigger value="transactions">expense report</TabsTrigger>
          </TabsList>

          {/* 1. Cash flow */}
          <TabsContent value="cashflow">
            <Panel title="income vs expenses" meta="last 12 months" statusDotColor="accent">
              {cashflow.isLoading ? (
                <Skeleton className="h-64" />
              ) : (
                <IncomeExpenseBar data={cashflow.data?.cashflow ?? []} />
              )}
            </Panel>
            <SavingsRatePanel cashflow={cashflow.data?.cashflow ?? []} loading={cashflow.isLoading} />
          </TabsContent>

          {/* 1b. Reserve & allocation */}
          <TabsContent value="allocation">
            <ReserveAllocationTab />
          </TabsContent>

          {/* 2. Categories */}
          <TabsContent value="categories">
            <Panel title="category monthly trend" meta="last 12 months" statusDotColor="accent">
              {categories.isLoading ? (
                <Skeleton className="h-72" />
              ) : (
                <CategoryTrendLine
                  data={categories.data?.categories ?? []}
                  categories={categoryNames(categories.data?.categories ?? [])}
                />
              )}
            </Panel>
            <p className="mt-2 text-xs text-text-label">
              top-merchants + outlier detection need transaction-level data (pending)
            </p>
          </TabsContent>

          {/* 3. Net worth */}
          <TabsContent value="networth">
            <NetWorthTab />
          </TabsContent>

          {/* 4. Forecast */}
          <TabsContent value="forecast">
            <ForecastTab />
          </TabsContent>

          {/* 5. Budget */}
          <TabsContent value="budget">
            <BudgetTab categories={categories.data?.categories ?? []} loading={categories.isLoading} />
          </TabsContent>

          {/* 6. Tax */}
          <TabsContent value="tax">
            <TaxTab />
          </TabsContent>

          {/* 7. Expense Report */}
          <TabsContent value="transactions">
            <ExpenseReportTab />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

function SavingsRatePanel({
  cashflow,
  loading,
}: {
  cashflow: { month: string; income: number; expenses: number }[]
  loading: boolean
}) {
  if (loading) return null
  const rows = cashflow.map((c) => ({
    month: c.month,
    rate: c.income ? ((c.income - c.expenses) / c.income) * 100 : null,
  }))
  return (
    <Panel title="savings rate" meta="per month" statusDotColor="success" className="mt-4">
      <div className="flex flex-wrap gap-3">
        {rows.map((r) => (
          <div key={r.month} className="rounded-sm border border-border px-2 py-1">
            <div className="font-mono text-xs text-text-label">{r.month}</div>
            <NumberDisplay value={r.rate} format="percent" signed />
          </div>
        ))}
      </div>
    </Panel>
  )
}

// 1b. Reserve & allocation — surplus split (Notgroschen target + 70/30 waterfall)
// and actual-vs-recommended TR contribution tracking. Data: /api/money/allocation/{month}.
function ReserveAllocationTab() {
  const months = useMoneyAvailableMonths()
  const allMonths = months.data?.months ?? []
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)

  const idx = selectedIdx !== null ? selectedIdx : allMonths.length - 1
  const month = allMonths[idx] ?? null
  const prevMonth = idx > 0 ? allMonths[idx - 1] : null

  const alloc = useMoneyAllocation(month)
  const prevAlloc = useMoneyAllocation(prevMonth)

  const monthLabel = month
    ? new Date(month + "-01").toLocaleString("en-US", { month: "long", year: "numeric" })
    : undefined
  const canPrev = idx > 0
  const canNext = idx < allMonths.length - 1

  const data = alloc.data
  const prevData = prevAlloc.data
  const reserveFull = (data?.reserve.percent_filled ?? 0) >= 100 && data?.split_recommendation.to_reserve === 0

  return (
    <div className="space-y-4">
      {/* Month picker (same prev/next idiom as the Overview monthly P&L panel) */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSelectedIdx(Math.max(0, idx - 1))}
            disabled={!canPrev}
            className="rounded px-1.5 py-0.5 text-xs text-text-label hover:text-text-secondary disabled:opacity-30 transition-colors"
          >
            ←
          </button>
          <span className="font-mono text-xs text-text-secondary tabular-nums min-w-[110px] text-center">
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
      </div>

      {(months.isLoading || alloc.isLoading) ? (
        <Skeleton className="h-96" />
      ) : !data ? (
        <Panel title="reserve & allocation" statusDotColor="muted">
          <p className="text-sm text-text-label">no data for this month.</p>
        </Panel>
      ) : (
        <>
          {/* KPI row: real income, expenses, investable surplus, savings rate — each vs last month */}
          <div className="grid gap-3 sm:grid-cols-4">
            <KpiTile
              label="real income"
              value={data.investable_income}
              previous={prevData?.investable_income}
              format="currency"
            />
            <KpiTile
              label="expenses"
              value={data.expenses.total}
              previous={prevData?.expenses.total}
              format="currency"
              invert
            />
            <KpiTile
              label="investable surplus"
              value={data.investable_surplus}
              previous={prevData?.investable_surplus}
              format="currency"
            />
            <KpiTile
              label="savings rate"
              value={data.savings_rate}
              previous={prevData?.savings_rate}
              format="percent"
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <ReserveGauge reserve={data.reserve} />
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

          <IncomeByTypePanel incomeByType={data.income_by_type} />
        </>
      )}
    </div>
  )
}

function KpiTile({
  label,
  value,
  previous,
  format,
  invert,
}: {
  label: string
  value: number | null
  previous: number | null | undefined
  format: "currency" | "percent"
  invert?: boolean
}) {
  const delta = value != null && previous != null ? value - previous : null
  const deltaUp = delta != null && delta > 0
  const deltaDown = delta != null && delta < 0
  const good = invert ? deltaDown : deltaUp
  const bad = invert ? deltaUp : deltaDown
  const deltaColor = delta == null ? "text-text-label" : good ? "text-success" : bad ? "text-danger" : "text-text-label"

  return (
    <Panel title={label} statusDotColor="accent" className="!py-3">
      <NumberDisplay
        value={format === "percent" && value != null ? value * 100 : value}
        format={format}
        emphasized
      />
      <div className={cn("mt-1 font-mono text-xs tabular-nums", deltaColor)}>
        {delta == null ? (
          <span className="text-text-label">vs last mo —</span>
        ) : format === "percent" ? (
          `vs last mo ${delta >= 0 ? "+" : ""}${(delta * 100).toFixed(1)} pp`
        ) : (
          `vs last mo ${delta >= 0 ? "+" : ""}${formatCurrency(delta)}`
        )}
      </div>
    </Panel>
  )
}

function ReserveGauge({ reserve }: { reserve: AllocationReserveStatus }) {
  const balance = reserve.reserve_balance
  const pct = reserve.percent_filled
  const full = (pct ?? 0) >= 100

  return (
    <Panel
      title="reserve (notgroschen)"
      meta={`target ${formatCurrency(reserve.target)}`}
      statusDotColor={balance == null ? "muted" : full ? "success" : "warning"}
    >
      {balance == null ? (
        <p className="text-sm text-text-label">
          no Reserve Balance recorded yet — add it to the Bank sheet's "Reserve Balance (€)" column.
        </p>
      ) : (
        <div className="space-y-2.5">
          <NumberDisplay value={balance} format="currency" emphasized className="text-2xl" />
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-bg-muted">
            <div
              className={cn("h-full rounded-full transition-[width]", full ? "bg-success" : "bg-accent")}
              style={{ width: `${Math.min(100, pct ?? 0)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-text-label">
            <span>{pct}% filled</span>
            <span>
              {full || !reserve.remaining_to_target
                ? "fully funded"
                : `${formatCurrency(reserve.remaining_to_target)} remaining`}
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
  split: AllocationSplitRecommendation
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
  contribution: ActualContribution
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
    <Panel
      title="actual TR contribution vs recommended"
      statusDotColor={contribution.reliable ? "accent" : "warning"}
    >
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
              <Input
                mono
                type="number"
                value={overrideInput}
                onChange={(e) => setOverrideInput(e.target.value)}
                placeholder="e.g. 500"
              />
            </div>
            <Button size="sm" onClick={saveOverride} disabled={!overrideInput.trim() || setOverride.isPending}>
              save
            </Button>
          </div>
        )}

        <p className="text-xs text-text-label">
          depends on the TR statement parser being verified against a real statement — treat
          "estimated" values as best-effort, not fact, until then.
        </p>
      </div>
    </Panel>
  )
}

// Types that count toward investable surplus (core/config.py INVESTABLE_INCOME_TYPES).
// Display-only classification — the actual investable_income sum always comes
// from the backend; this just decides which badge a row gets.
const INVESTABLE_INCOME_TYPES = new Set(["salary", "freelance"])

function IncomeByTypePanel({ incomeByType }: { incomeByType: Record<string, number> }) {
  const entries = Object.entries(incomeByType).sort((a, b) => b[1] - a[1])
  const total = entries.reduce((s, [, v]) => s + v, 0)

  return (
    <Panel title="income by type" meta="salary/freelance count toward surplus" statusDotColor="accent">
      {entries.length === 0 ? (
        <p className="text-sm text-text-label">no income recorded this month.</p>
      ) : (
        <div className="space-y-2">
          {entries.map(([type, amount]) => {
            const pct = total > 0 ? (amount / total) * 100 : 0
            const investable = INVESTABLE_INCOME_TYPES.has(type)
            return (
              <div key={type} className="flex items-center gap-2 text-xs">
                <span className="w-28 shrink-0 text-text-secondary">{type}</span>
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

// 3. Net worth
function NetWorthTab() {
  const snap = useMoneySnapshot()
  const breakdown = useMemo(() => {
    const b = snap.data?.net_worth_breakdown ?? {}
    return Object.entries(b)
      .filter(([k, v]) => k.toLowerCase() !== "total" && typeof v === "number" && (v as number) > 0)
      .map(([name, value]) => ({ name, value: value as number }))
  }, [snap.data])

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="net worth" statusDotColor="success">
        {snap.isLoading ? (
          <Skeleton className="h-12" />
        ) : (
          <NumberDisplay value={snap.data?.net_worth} format="currency" emphasized className="text-2xl" />
        )}
      </Panel>
      <Panel title="composition" statusDotColor="accent">
        {snap.isLoading ? (
          <Skeleton className="h-48" />
        ) : breakdown.length === 0 ? (
          <p className="text-sm text-text-label">no breakdown available</p>
        ) : (
          <CategoryDonut data={breakdown} height={220} />
        )}
      </Panel>
      <p className="lg:col-span-2 text-xs text-text-label">
        net-worth-over-time chart needs the historical net_worth series (pending)
      </p>
    </div>
  )
}

// 4. Forecast
function ForecastTab() {
  const runSkill = useRunSkill()
  const [text, setText] = useState("")
  return (
    <Panel title="cash-flow forecast" statusDotColor="accent">
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="e.g. evercore base €X + bonus €Y, ffm rent €Z, cut subscriptions by €W..."
        rows={4}
      />
      <div className="mt-2 flex justify-end">
        <Button
          disabled={!text.trim() || runSkill.isPending}
          onClick={() =>
            runSkill.mutate(
              { skill: "forecast_cash_flow", args: { scenario_description: text.trim() }, label: "Cash-flow forecast" },
              {
                onSuccess: (r) => {
                  setText("")
                  toast.success("started in background — see background runs", r.run_id)
                },
                onError: (e) => toast.error("failed to start", String(e)),
              },
            )
          }
        >
          run forecast
        </Button>
      </div>
    </Panel>
  )
}

// 5. Budget — local targets vs last-month actuals
function BudgetTab({
  categories,
  loading,
}: {
  categories: Record<string, string | number | null>[]
  loading: boolean
}) {
  const actuals = lastCategoryBreakdown(categories)
  const [targets, setTargets] = useState<Record<string, string>>({})

  if (loading) return <Skeleton className="h-40" />
  if (actuals.length === 0)
    return (
      <Panel title="budget" statusDotColor="muted">
        <p className="text-sm text-text-label">no category data</p>
      </Panel>
    )

  return (
    <Panel title="budget vs actual" meta="last month" statusDotColor="accent">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>category</TableHead>
            <TableHead>actual</TableHead>
            <TableHead>target</TableHead>
            <TableHead>variance</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {actuals.map((c) => {
            const target = parseFloat(targets[c.name] ?? "")
            const variance = Number.isFinite(target) ? target - c.value : null
            return (
              <TableRow key={c.name}>
                <TableCell className="text-text">{c.name}</TableCell>
                <TableCell className="font-mono">{formatCurrency(c.value)}</TableCell>
                <TableCell>
                  <Input
                    mono
                    className="h-7 w-28"
                    value={targets[c.name] ?? ""}
                    onChange={(e) => setTargets((t) => ({ ...t, [c.name]: e.target.value }))}
                    placeholder="—"
                  />
                </TableCell>
                <TableCell>
                  {variance == null ? (
                    <span className="text-text-label">—</span>
                  ) : (
                    <NumberDisplay value={variance} format="currency" signed />
                  )}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      <p className="mt-2 text-xs text-text-label">budget-target persistence pending (backend phase)</p>
    </Panel>
  )
}

// 7. Expense Report
const CATEGORY_COLORS: Record<string, string> = {
  Shopping: "bg-purple-500",
  Restaurants: "bg-orange-400",
  Transport: "bg-blue-400",
  Travel: "bg-cyan-400",
  Entertainment: "bg-pink-400",
  Groceries: "bg-green-400",
  Subscriptions: "bg-yellow-400",
  Utilities: "bg-gray-400",
  Health: "bg-red-400",
  Rent: "bg-indigo-500",
  Other: "bg-text-label",
}

function ExpenseReportTab() {
  const { data: monthsData, isLoading: monthsLoading } = useMoneyAvailableMonths()
  const months = monthsData?.months ?? []
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null)
  const [catFilter, setCatFilter] = useState<string>("all")

  // Auto-select latest month once loaded
  const effectiveMonth = selectedMonth ?? (months.length ? months[months.length - 1] : null)

  const { data: report, isLoading: reportLoading } = useMoneyReport(effectiveMonth)

  const totalExpenses = report?.expenses.total ?? 0
  const totalIncome = report?.income.total ?? 0
  const net = report?.net ?? 0

  const filteredTx = (report?.transactions ?? []).filter(
    (t) => catFilter === "all" || t.category === catFilter,
  )

  if (monthsLoading) return <Skeleton className="h-96" />

  return (
    <div className="space-y-4">
      {/* Month picker */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-text-label">month</span>
        <div className="flex flex-wrap gap-1">
          {months.map((m) => (
            <button
              key={m}
              onClick={() => { setSelectedMonth(m); setCatFilter("all") }}
              className={`rounded px-2 py-0.5 font-mono text-xs transition-colors ${
                m === effectiveMonth
                  ? "bg-accent text-bg"
                  : "bg-surface text-text-secondary hover:bg-border"
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {reportLoading && <Skeleton className="h-64" />}

      {report && (
        <>
          {/* Top KPIs */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Panel title="income" statusDotColor="success" className="!py-3">
              <NumberDisplay value={totalIncome} format="currency" emphasized />
            </Panel>
            <Panel title="expenses" statusDotColor="danger" className="!py-3">
              <NumberDisplay value={totalExpenses} format="currency" emphasized />
            </Panel>
            <Panel title="net" statusDotColor={net >= 0 ? "success" : "danger"} className="!py-3">
              <NumberDisplay value={net} format="currency" emphasized signed />
            </Panel>
            <Panel title="savings rate" statusDotColor="accent" className="!py-3">
              <NumberDisplay
                value={report.savings_rate != null ? report.savings_rate * 100 : null}
                format="percent"
                emphasized
                signed
              />
            </Panel>
          </div>

          {/* Income breakdown + Expense by category side by side */}
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Income */}
            <Panel title="revenue" statusDotColor="success">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>source</TableHead>
                    <TableHead className="text-right">amount</TableHead>
                    <TableHead className="text-right">share</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {[
                    { label: "salary", amount: report.income.salary },
                    { label: "other income", amount: report.income.other },
                  ]
                    .filter((r) => r.amount > 0)
                    .map((r) => (
                      <TableRow key={r.label}>
                        <TableCell className="text-text">{r.label}</TableCell>
                        <TableCell className="text-right font-mono">
                          {formatCurrency(r.amount)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-text-label">
                          {totalIncome ? `${((r.amount / totalIncome) * 100).toFixed(0)}%` : "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  <TableRow className="border-t border-border font-semibold">
                    <TableCell>total</TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(totalIncome)}
                    </TableCell>
                    <TableCell />
                  </TableRow>
                </TableBody>
              </Table>
            </Panel>

            {/* Expenses by category */}
            <Panel title="expenses by category" statusDotColor="danger">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>category</TableHead>
                    <TableHead className="text-right">amount</TableHead>
                    <TableHead className="text-right">share</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.expenses.by_category.map((c) => {
                    const pct = totalExpenses ? (c.amount / totalExpenses) * 100 : 0
                    const color = CATEGORY_COLORS[c.category] ?? CATEGORY_COLORS.Other
                    return (
                      <TableRow
                        key={c.category}
                        className="cursor-pointer hover:bg-surface"
                        onClick={() =>
                          setCatFilter((f) => (f === c.category ? "all" : c.category))
                        }
                      >
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className={`h-2 w-2 rounded-full ${color}`} />
                            <span className="text-text">{c.category}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {formatCurrency(c.amount)}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="h-1.5 w-16 rounded-full bg-border">
                              <div
                                className={`h-full rounded-full ${color}`}
                                style={{ width: `${Math.min(pct, 100)}%` }}
                              />
                            </div>
                            <span className="w-8 text-right font-mono text-xs text-text-label">
                              {pct.toFixed(0)}%
                            </span>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                  <TableRow className="border-t border-border font-semibold">
                    <TableCell>total</TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(totalExpenses)}
                    </TableCell>
                    <TableCell />
                  </TableRow>
                </TableBody>
              </Table>
              <p className="mt-1 text-xs text-text-label">click a row to filter transactions below</p>
            </Panel>
          </div>

          {/* Transaction ledger */}
          <Panel
            title={catFilter === "all" ? "all transactions" : `transactions · ${catFilter}`}
            meta={`${filteredTx.length} rows`}
            statusDotColor="muted"
          >
            {catFilter !== "all" && (
              <button
                onClick={() => setCatFilter("all")}
                className="mb-2 text-xs text-accent hover:underline"
              >
                ← clear filter
              </button>
            )}
            <div className="max-h-96 overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>date</TableHead>
                    <TableHead>description</TableHead>
                    <TableHead>category</TableHead>
                    <TableHead>card</TableHead>
                    <TableHead className="text-right">amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredTx.map((t, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-mono text-xs text-text-label">{t.date}</TableCell>
                      <TableCell className="max-w-[220px] truncate text-sm">{t.description}</TableCell>
                      <TableCell>
                        <span className="rounded bg-surface px-1.5 py-0.5 text-xs text-text-secondary">
                          {t.category}
                        </span>
                      </TableCell>
                      <TableCell className="text-xs text-text-label">{t.card}</TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {formatCurrency(t.amount)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Panel>
        </>
      )}
    </div>
  )
}

// 6. Tax — A current state · B scenario workshop · C checklist
function TaxTab() {
  const taxScenario = useTaxScenario()
  const { data: projects } = useProjects()
  const [text, setText] = useState("")
  const [saveTo, setSaveTo] = useState<string>("__default__")

  function run() {
    const scenario = text.trim()
    if (!scenario) return
    taxScenario.mutate(
      {
        scenario_description: scenario,
        save_to_project: saveTo === "__default__" ? null : saveTo,
      },
      {
        onSuccess: (r) => {
          setText("")
          toast.success("started in background — see background runs", r.run_id)
        },
        onError: (e) => toast.error("failed to start", String(e)),
      },
    )
  }

  return (
    <div className="space-y-4">
      {/* A · investment tax integration (Phase 15d) — Abgeltungsteuer estimate,
          crypto Spekulationsfrist countdown, capital-allocation suggestions. */}
      <TaxIntegrationPanels />

      {/* B */}
      <Panel title="b · run a tax scenario" statusDotColor="accent">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="describe the hypothetical — talk to it like a cfo. e.g. buy €450k flat, 20% down, €30k repairs, intent to rent — 10-year tax impact?"
          rows={4}
        />
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <div className="min-w-[16rem] flex-1">
            <div className="label mb-1">save analysis to</div>
            <Select value={saveTo} onValueChange={setSaveTo}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__default__">default · 2_Personal/03_Steuern/</SelectItem>
                {(projects ?? []).map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.id} {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={run} disabled={!text.trim() || taxScenario.isPending}>
            run scenario
          </Button>
        </div>
      </Panel>

      {/* C */}
      <Panel title="c · year-end checklist" statusDotColor="muted">
        <ul className="space-y-1 text-sm text-text-secondary">
          {YEAR_END_CHECKLIST.map((item) => (
            <li key={item} className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-text-label" />
              {item}
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  )
}
