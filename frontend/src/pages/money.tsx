import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { NumberDisplay } from "@/components/ui/number-display"
import { MetricPanel } from "@/components/finance/metric-panel"
import { IncomeExpenseBar, CategoryDonut } from "@/components/charts/finance-charts"
import { useMoneySnapshot, useMoneyCashflow, useMoneyCategories } from "@/hooks/useFinance"
import { useTravel } from "@/hooks/useCalendar"
import { HARD_DATES } from "@/lib/hard-dates"
import { countdownLabel } from "@/lib/status"
import { lastCategoryBreakdown } from "@/lib/money"

export function Money() {
  const snap = useMoneySnapshot()
  const cashflow = useMoneyCashflow(6)
  const categories = useMoneyCategories(6)
  const travel = useTravel()

  const breakdown = lastCategoryBreakdown(categories.data?.categories ?? [])

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">money</h1>
        <Button asChild variant="secondary" size="sm">
          <a href="/workspace/money" target="_blank" rel="noopener noreferrer">
            open workspace ↗
          </a>
        </Button>
      </div>

      {/* Top metrics */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricPanel
          label="cash"
          value={
            snap.isLoading ? <Skeleton className="h-7 w-28" /> : (
              <NumberDisplay value={snap.data?.cash_balance} format="currency" emphasized animate />
            )
          }
        />
        <MetricPanel
          label="net worth"
          dotColor="success"
          value={
            snap.isLoading ? <Skeleton className="h-7 w-28" /> : (
              <NumberDisplay value={snap.data?.net_worth} format="currency" emphasized animate />
            )
          }
        />
        <MetricPanel
          label="monthly burn"
          dotColor="warning"
          value={
            snap.isLoading ? <Skeleton className="h-7 w-24" /> : (
              <NumberDisplay value={snap.data?.monthly_burn} format="currency" />
            )
          }
        />
        <MetricPanel
          label="runway"
          dotColor="accent"
          value={
            snap.isLoading ? <Skeleton className="h-7 w-16" /> : (
              <span>
                <NumberDisplay value={snap.data?.runway_months} decimals={1} />
                <span className="ml-1 text-sm text-text-secondary">mo</span>
              </span>
            )
          }
        />
      </div>

      {/* Charts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="income vs expenses" meta="last 6 months" statusDotColor="accent">
          {cashflow.isLoading ? (
            <Skeleton className="h-64" />
          ) : (
            <IncomeExpenseBar data={cashflow.data?.cashflow ?? []} />
          )}
        </Panel>
        <Panel title="spending breakdown" meta="last month" statusDotColor="accent">
          {categories.isLoading ? (
            <Skeleton className="h-64" />
          ) : breakdown.length === 0 ? (
            <p className="text-sm text-text-label">no category data</p>
          ) : (
            <CategoryDonut data={breakdown} />
          )}
        </Panel>
      </div>

      {/* Big upcoming */}
      <Panel title="big upcoming" statusDotColor="warning">
        <ul className="space-y-1.5 text-sm">
          {HARD_DATES.map((d) => (
            <li key={d.label} className="flex items-center justify-between gap-2">
              <span className="text-text">{d.label}</span>
              <span className="font-mono text-xs text-accent">{countdownLabel(d.date)}</span>
            </li>
          ))}
          {(travel.data?.trips ?? []).map((t, i) => (
            <li key={`trip-${i}`} className="flex items-center justify-between gap-2">
              <span className="text-text">{String(t.destination ?? t.title ?? "trip")}</span>
              <span className="font-mono text-xs text-text-secondary">
                {t.days_until != null ? `in ${t.days_until}d` : String(t.date ?? "")}
              </span>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  )
}
