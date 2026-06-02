import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
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
import { IncomeExpenseBar, CategoryDonut, CategoryTrendLine } from "@/components/charts/finance-charts"
import { TaxIntegrationPanels } from "@/components/finance/tax-panel"
import {
  useMoneySnapshot,
  useMoneyCashflow,
  useMoneyCategories,
} from "@/hooks/useFinance"
import { useProjects } from "@/hooks/useProjects"
import { useRunSkill, useTaxScenario } from "@/hooks/useSkills"
import { categoryNames, lastCategoryBreakdown } from "@/lib/money"
import { openInOs } from "@/lib/open-in-os"
import { formatCurrency } from "@/lib/utils"
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
          <Link to="/money" className="font-mono text-xs text-text-secondary hover:text-accent">
            ← money
          </Link>
        </div>

        <Tabs defaultValue="cashflow">
          <TabsList>
            <TabsTrigger value="cashflow">cash flow</TabsTrigger>
            <TabsTrigger value="categories">categories</TabsTrigger>
            <TabsTrigger value="networth">net worth</TabsTrigger>
            <TabsTrigger value="forecast">forecast</TabsTrigger>
            <TabsTrigger value="budget">budget</TabsTrigger>
            <TabsTrigger value="tax">tax</TabsTrigger>
            <TabsTrigger value="transactions">transactions</TabsTrigger>
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

          {/* 7. Transactions */}
          <TabsContent value="transactions">
            <Panel title="transactions ledger" statusDotColor="muted">
              <p className="mb-3 text-sm text-text-label">
                full ledger endpoint pending — finance_tracker.xlsx transactions sheet
                is not yet exposed via the api.
              </p>
              <Button variant="secondary" size="sm" onClick={() => openInOs("Finance_Tracker.xlsx")}>
                open in excel
              </Button>
            </Panel>
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
