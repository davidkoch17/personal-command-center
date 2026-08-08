import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { NumberDisplay } from "@/components/ui/number-display"
import { MetricPanel } from "@/components/finance/metric-panel"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  ReserveTrajectoryLine,
  ReserveInvestSplitBar,
  SavingsIncomeStabilityTrend,
} from "@/components/charts/finance-charts"
import {
  useCashflowExpectedIncome,
  useCashflowForecast,
  useCashflowRunwayScenarios,
  useCashflowTrends,
  useSetCashflowExpectedIncome,
  type CashflowRunwayScenariosResponse,
} from "@/hooks/useCashflow"
import { formatCurrency } from "@/lib/utils"

function monthLabel(month: string): string {
  return new Date(`${month}-01`).toLocaleString("en-US", { month: "long", year: "numeric" })
}

/**
 * Cash Flow → Forecast — forward cashflow projection (recurring income minus
 * committed bills, carried through the 70/30 reserve waterfall), runway
 * scenarios, and the savings-rate / income-stability trend.
 */
export function ForecastTab() {
  const forecast = useCashflowForecast(6)
  const scenarios = useCashflowRunwayScenarios()
  const trends = useCashflowTrends(12)
  const expectedIncome = useCashflowExpectedIncome()
  const setExpectedIncome = useSetCashflowExpectedIncome()

  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState("")

  function startEdit() {
    setValue(expectedIncome.data?.monthly_amount != null ? String(expectedIncome.data.monthly_amount) : "")
    setEditing(true)
  }

  function save() {
    const trimmed = value.trim()
    const num = parseFloat(trimmed)
    setExpectedIncome.mutate(trimmed === "" ? null : Number.isFinite(num) ? num : null, {
      onSuccess: () => setEditing(false),
    })
  }

  const lastMonth = forecast.data?.months[forecast.data.months.length - 1]?.month ?? forecast.data?.base_month
  const projectedSurplus = forecast.data ? forecast.data.recurring_income - forecast.data.committed_bills : null

  return (
    <div className="space-y-4">
      {forecast.isLoading ? (
        <Skeleton className="h-96" />
      ) : !forecast.data ? (
        <Panel title="forecast" statusDotColor="muted">
          <EmptyState message="no ledger history yet — add income/expenses to project forward." />
        </Panel>
      ) : (
        <>
          <Panel
            title="forecast assumptions"
            meta={`base month ${monthLabel(forecast.data.base_month)}`}
            statusDotColor="accent"
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <div className="label mb-1">recurring income</div>
                {editing ? (
                  <div className="flex items-center gap-2">
                    <Input
                      mono
                      className="h-8 w-32"
                      value={value}
                      onChange={(e) => setValue(e.target.value)}
                      placeholder="e.g. 5000"
                    />
                    <Button size="sm" onClick={save} disabled={setExpectedIncome.isPending}>
                      save
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>
                      cancel
                    </Button>
                  </div>
                ) : (
                  <button onClick={startEdit} className="flex items-center gap-2">
                    <NumberDisplay value={forecast.data.recurring_income} format="currency" emphasized className="text-xl" />
                    <span className="text-xs text-text-label hover:text-accent">
                      {expectedIncome.data?.monthly_amount != null ? "· manual override · edit" : "· salary avg · set override"}
                    </span>
                  </button>
                )}
              </div>
              <div>
                <div className="label mb-1">committed bills</div>
                <NumberDisplay value={forecast.data.committed_bills} format="currency" className="text-xl" />
                <div className="mt-1 text-xs text-text-label">trailing avg of fixed-category spend</div>
              </div>
            </div>
          </Panel>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <MetricPanel
              label="reserve-fill date"
              value={forecast.data.reserve_fill_month ? monthLabel(forecast.data.reserve_fill_month) : "—"}
              caption={forecast.data.reserve_fill_month ? undefined : "not within projection horizon"}
              dotColor={forecast.data.reserve_fill_month ? "success" : "muted"}
            />
            <MetricPanel
              label="investing begins"
              value={forecast.data.invest_start_month ? monthLabel(forecast.data.invest_start_month) : "—"}
              caption={forecast.data.invest_start_month ? undefined : "no surplus projected yet"}
              dotColor={forecast.data.invest_start_month ? "invest" : "muted"}
            />
            <MetricPanel
              label="projected monthly surplus"
              value={<NumberDisplay value={projectedSurplus} format="currency" signed className="text-2xl" />}
              dotColor={projectedSurplus != null && projectedSurplus >= 0 ? "success" : "danger"}
            />
          </div>

          <Panel
            title="reserve fill trajectory"
            meta={lastMonth ? `through ${monthLabel(lastMonth)}` : undefined}
            statusDotColor="success"
          >
            <ReserveTrajectoryLine data={forecast.data.months} target={forecast.data.reserve_target} />
          </Panel>

          <Panel title="monthly split — reserve vs. invest" statusDotColor="invest">
            <ReserveInvestSplitBar data={forecast.data.months} />
          </Panel>
        </>
      )}

      <Panel title="runway scenarios" statusDotColor="warning">
        {scenarios.isLoading ? (
          <Skeleton className="h-24" />
        ) : !scenarios.data || scenarios.data.base.monthly_burn == null ? (
          <EmptyState message="no ledger history yet to estimate a burn rate from." />
        ) : (
          <RunwayScenarios data={scenarios.data} />
        )}
      </Panel>

      <Panel title="savings rate & income stability" meta="last 12 months" statusDotColor="accent">
        {trends.isLoading ? <Skeleton className="h-64" /> : <SavingsIncomeStabilityTrend data={trends.data?.trends ?? []} />}
      </Panel>
    </div>
  )
}

function RunwayScenarios({ data }: { data: CashflowRunwayScenariosResponse }) {
  const rows = [
    { label: "current pace", burn: data.base.monthly_burn, months: data.base.months_total, until: data.base.cash_lasts_until },
    {
      label: "cut variable 25%",
      burn: data.cut_variable_25?.monthly_burn ?? null,
      months: data.cut_variable_25?.months_total ?? null,
      until: data.cut_variable_25?.cash_lasts_until ?? null,
    },
    {
      label: "cut variable 50%",
      burn: data.cut_variable_50?.monthly_burn ?? null,
      months: data.cut_variable_50?.months_total ?? null,
      until: data.cut_variable_50?.cash_lasts_until ?? null,
    },
  ]
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {rows.map((r) => (
        <div key={r.label} className="rounded-sm border border-border p-3">
          <div className="text-xs text-text-label">{r.label}</div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <NumberDisplay value={r.months} decimals={1} className="text-xl" />
            <span className="text-xs text-text-label">months</span>
          </div>
          <div className="mt-1 text-xs text-text-secondary">
            burn {formatCurrency(r.burn)}/mo{r.until ? ` · lasts until ${r.until}` : ""}
          </div>
        </div>
      ))}
    </div>
  )
}
