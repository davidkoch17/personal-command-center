import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { NumberDisplay } from "@/components/ui/number-display"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { StatusDot, type StatusColor } from "@/components/ui/status-dot"
import { IncomeExpenseNetBar } from "@/components/charts/finance-charts"
import {
  useCashflowAccounts,
  useCashflowAlerts,
  useCashflowForecast,
  useCashflowMonths,
  useCashflowOverview,
  useCashflowRunway,
  useCashflowTrend,
  useDeleteCashflowAccount,
  useSetCashflowAccount,
  useSetCashflowReserveTarget,
  type CashflowAccount,
  type CashflowAlert,
  type CashflowAlertSeverity,
  type CashflowOverviewResponse,
  type CashflowTopCategory,
} from "@/hooks/useCashflow"
import { MonthPicker } from "./month-picker"
import { ReviewQueue } from "./review-queue"
import { cn, formatCurrency, formatPercent } from "@/lib/utils"

function monthLabel(month: string): string {
  return new Date(`${month}-01`).toLocaleString("en-US", { month: "long", year: "numeric" })
}

export function OverviewTab() {
  const monthsQ = useCashflowMonths()
  const months = monthsQ.data?.months ?? []
  const [selected, setSelected] = useState<string | null>(null)
  const month = selected ?? (months.length ? months[months.length - 1] : null)

  const overview = useCashflowOverview(month)
  const trend = useCashflowTrend(6)

  return (
    <div className="space-y-4">
      <MonthPicker months={months} month={month} onChange={setSelected} />

      {month && <AlertsStrip month={month} />}

      <ReviewQueue />

      {monthsQ.isLoading || overview.isLoading ? (
        <Skeleton className="h-96" />
      ) : !overview.data || !month ? (
        <Panel title="overview" statusDotColor="muted">
          <EmptyState message="no data yet — hand me a bank/card statement, receipt, or screenshot and I'll add it to the ledger." />
        </Panel>
      ) : (
        <>
          <AccountsStrip reserveTarget={overview.data.reserve.target} />

          <RunwayBand />

          <KpiRow data={overview.data} month={month} />

          <ReservePanel data={overview.data} />

          <Panel title="income vs expenses" meta="last 6 months" statusDotColor="accent">
            {trend.isLoading ? <Skeleton className="h-64" /> : <IncomeExpenseNetBar data={trend.data?.trend ?? []} />}
          </Panel>

          <TopCategoriesPanel data={overview.data} />
        </>
      )}
    </div>
  )
}

// --- Alerts strip -----------------------------------------------------------
// Only rendered when something is flagged (category spike, new/rising
// recurring charge, low runway, reserve milestone) — no empty-state noise.

const ALERT_SEVERITY_DOT: Record<CashflowAlertSeverity, StatusColor> = {
  high: "danger",
  medium: "warning",
  low: "accent",
}

const ALERT_SEVERITY_STYLE: Record<CashflowAlertSeverity, string> = {
  high: "border-danger/40 bg-danger/10",
  medium: "border-warning/40 bg-warning/10",
  low: "border-accent/30 bg-accent/10",
}

function AlertsStrip({ month }: { month: string }) {
  const alertsQ = useCashflowAlerts(month)
  const navigate = useNavigate()
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())

  const alerts = (alertsQ.data?.alerts ?? []).filter((a) => !dismissed.has(a.id))
  if (alerts.length === 0) return null

  return (
    <div className="space-y-1.5">
      {alerts.map((a) => (
        <AlertRow
          key={a.id}
          alert={a}
          onOpen={() => navigate(`/cashflow?tab=${a.tab}`)}
          onDismiss={() => setDismissed((prev) => new Set(prev).add(a.id))}
        />
      ))}
    </div>
  )
}

function AlertRow({ alert, onOpen, onDismiss }: { alert: CashflowAlert; onOpen: () => void; onDismiss: () => void }) {
  return (
    <div className={cn("flex items-center justify-between gap-3 rounded-sm border px-3 py-2", ALERT_SEVERITY_STYLE[alert.severity])}>
      <button onClick={onOpen} className="flex flex-1 items-center gap-2 text-left">
        <StatusDot color={ALERT_SEVERITY_DOT[alert.severity]} />
        <span className="text-xs text-text-secondary">{alert.message}</span>
      </button>
      <button
        onClick={(e) => {
          e.stopPropagation()
          onDismiss()
        }}
        aria-label="dismiss alert"
        className="shrink-0 text-xs text-text-label hover:text-text-secondary"
      >
        ×
      </button>
    </div>
  )
}

// --- Accounts strip -------------------------------------------------------

function AccountsStrip({ reserveTarget }: { reserveTarget: number }) {
  const accountsQ = useCashflowAccounts()
  const setAccount = useSetCashflowAccount()
  const deleteAccount = useDeleteCashflowAccount()
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState("")
  const [balance, setBalance] = useState("")
  const [isReserve, setIsReserve] = useState(false)

  const accounts = accountsQ.data?.accounts ?? []
  const totalCash = accountsQ.data?.total_cash ?? 0

  function save() {
    const num = parseFloat(balance)
    if (!name.trim() || !Number.isFinite(num)) return
    setAccount.mutate(
      { name: name.trim(), balance: num, is_reserve: isReserve },
      {
        onSuccess: () => {
          setAdding(false)
          setName("")
          setBalance("")
          setIsReserve(false)
        },
      },
    )
  }

  return (
    <Panel
      title="accounts"
      meta={accounts.length ? `${formatCurrency(totalCash)} total cash` : undefined}
      statusDotColor={accounts.length ? "accent" : "muted"}
    >
      {accountsQ.isLoading ? (
        <Skeleton className="h-10" />
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {accounts.length === 0 && !adding && <EmptyState message="no accounts recorded yet." />}
          {accounts.map((a) => (
            <AccountChip
              key={a.name}
              account={a}
              reserveTarget={reserveTarget}
              onDelete={() => deleteAccount.mutate(a.name)}
            />
          ))}
          {!adding && (
            <button
              onClick={() => setAdding(true)}
              className="rounded-sm border border-dashed border-border px-3 py-1.5 text-xs text-text-label hover:border-accent hover:text-accent"
            >
              + add account
            </button>
          )}
        </div>
      )}
      {adding && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Input className="h-8 w-36" placeholder="account name" value={name} onChange={(e) => setName(e.target.value)} />
          <Input
            mono
            className="h-8 w-28"
            placeholder="balance"
            value={balance}
            onChange={(e) => setBalance(e.target.value)}
          />
          <label className="flex items-center gap-1.5 text-xs text-text-label">
            <input type="checkbox" checked={isReserve} onChange={(e) => setIsReserve(e.target.checked)} />
            reserve
          </label>
          <Button size="sm" onClick={save} disabled={!name.trim() || !balance.trim() || setAccount.isPending}>
            save
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setAdding(false)}>
            cancel
          </Button>
        </div>
      )}
    </Panel>
  )
}

function AccountChip({
  account,
  reserveTarget,
  onDelete,
}: {
  account: CashflowAccount
  reserveTarget: number
  onDelete: () => void
}) {
  const setAccount = useSetCashflowAccount()
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(String(account.balance))

  function save() {
    const num = parseFloat(value)
    if (!Number.isFinite(num)) return
    setAccount.mutate(
      { name: account.name, balance: num, is_reserve: account.is_reserve },
      { onSuccess: () => setEditing(false) },
    )
  }

  const pct = account.is_reserve && reserveTarget > 0 ? Math.min(100, Math.round((account.balance / reserveTarget) * 100)) : null
  const full = pct != null && pct >= 100

  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-sm border px-3 py-1.5",
        account.is_reserve
          ? full
            ? "border-success/40 bg-success/10"
            : "border-warning/40 bg-warning/10"
          : "border-border bg-bg-panel",
      )}
    >
      <span className="text-xs font-medium text-text-secondary">{account.name}</span>
      {editing ? (
        <>
          <Input mono className="h-6 w-20 text-xs" value={value} onChange={(e) => setValue(e.target.value)} />
          <button onClick={save} className="text-xs text-accent">
            save
          </button>
        </>
      ) : (
        <button onClick={() => setEditing(true)} className="flex items-center gap-1.5">
          <NumberDisplay value={account.balance} format="currency" className="text-xs" />
          {pct != null && (
            <span className={cn("text-[10px]", full ? "text-success" : "text-warning")}>· {pct}% reserve</span>
          )}
        </button>
      )}
      <button onClick={onDelete} className="text-xs text-text-label hover:text-danger">
        ×
      </button>
    </div>
  )
}

// --- Runway band -----------------------------------------------------------

function formatDateLabel(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
}

function RunwayBand() {
  const runwayQ = useCashflowRunway()
  const data = runwayQ.data

  if (runwayQ.isLoading) return <Skeleton className="h-20" />
  if (!data || data.months_total == null || data.cash_lasts_until == null) {
    return (
      <Panel title="runway" statusDotColor="muted">
        <EmptyState message="no accounts or spending history yet to project runway from." />
      </Panel>
    )
  }

  const dotColor = data.months_total >= 3 ? "success" : data.months_total >= 1 ? "warning" : "danger"
  const drawdownPct =
    data.months_before_reserve_drawdown != null && data.months_total > 0
      ? Math.min(100, Math.round((data.months_before_reserve_drawdown / data.months_total) * 100))
      : null

  return (
    <Panel title="runway" meta={`${formatCurrency(data.monthly_burn ?? 0)}/mo burn`} statusDotColor={dotColor}>
      <div className="space-y-2">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span className="text-2xl font-mono tabular-nums text-text">cash lasts until {formatDateLabel(data.cash_lasts_until)}</span>
          <span className="text-xs text-text-label">
            ({data.months_total.toFixed(1)} mo at {formatCurrency(data.total_cash)} total cash)
          </span>
        </div>
        {drawdownPct != null && data.reserve_drawdown_date && (
          <div className="space-y-1">
            <div className="relative h-2 w-full overflow-hidden rounded-full bg-accent/30">
              <div className="absolute top-0 h-full w-0.5 -translate-x-1/2 bg-warning" style={{ left: `${drawdownPct}%` }} />
            </div>
            <div className="text-xs text-text-label">
              starts drawing into the {formatCurrency(data.reserve_balance)} reserve from {formatDateLabel(data.reserve_drawdown_date)}
            </div>
          </div>
        )}
      </div>
    </Panel>
  )
}

// --- KPI row ------------------------------------------------------------

function DeltaChip({ percent, goodDirection }: { percent: number | null; goodDirection: "up" | "down" }) {
  if (percent == null) return null
  const isUp = percent >= 0
  const isGood = goodDirection === "up" ? isUp : !isUp
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center rounded-full px-1.5 py-0.5 text-[11px] font-mono tabular-nums",
        isGood ? "bg-success/10 text-success" : "bg-danger/10 text-danger",
      )}
    >
      {formatPercent(percent, 1)} vs 3-mo avg
    </span>
  )
}

function KpiPanel({
  title,
  statusDotColor,
  period,
  value,
  format,
  signed,
  valueClassName,
  deltaPercent,
  goodDirection,
  subtext,
  mutedSubtext,
}: {
  title: string
  statusDotColor: "success" | "danger" | "accent" | "muted"
  period: string
  value: number | null
  format: "currency" | "percent"
  signed?: boolean
  valueClassName?: string
  deltaPercent?: number | null
  goodDirection?: "up" | "down"
  subtext?: string
  mutedSubtext?: string
}) {
  return (
    <Panel title={title} statusDotColor={statusDotColor} className="!py-3">
      <div className="space-y-1.5">
        <div className="text-[11px] text-text-label">{period}</div>
        <NumberDisplay value={value} format={format} signed={signed} className={cn("text-2xl", valueClassName)} />
        {deltaPercent !== undefined && goodDirection && <DeltaChip percent={deltaPercent} goodDirection={goodDirection} />}
        {subtext && <div className="text-[11px] text-text-label">{subtext}</div>}
        {mutedSubtext && <div className="text-[11px] text-text-label">{mutedSubtext}</div>}
      </div>
    </Panel>
  )
}

function KpiRow({ data, month }: { data: CashflowOverviewResponse; month: string }) {
  const period = `${monthLabel(month)} · vs 3-month average`
  const runwaySubtext = data.runway_months != null ? `runway ${data.runway_months.toFixed(1)} mo` : undefined

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <KpiPanel
        title="income"
        statusDotColor="success"
        period={period}
        value={data.income.total}
        format="currency"
        valueClassName="text-success"
        deltaPercent={data.income.delta_percent}
        goodDirection="up"
      />
      <KpiPanel
        title="expenses"
        statusDotColor="danger"
        period={period}
        value={data.expenses.total}
        format="currency"
        valueClassName="text-danger"
        deltaPercent={data.expenses.delta_percent}
        goodDirection="down"
      />
      <KpiPanel
        title="net"
        statusDotColor={data.net.total >= 0 ? "success" : "danger"}
        period={period}
        value={data.net.total}
        format="currency"
        signed
        deltaPercent={data.net.delta_percent}
        goodDirection="up"
        subtext={runwaySubtext}
      />
      <KpiPanel
        title="savings rate"
        statusDotColor="accent"
        period={period}
        value={data.savings_rate != null ? data.savings_rate * 100 : null}
        format="percent"
        signed
        mutedSubtext={data.savings_rate == null ? "income near €0" : undefined}
      />
    </div>
  )
}

// --- Reserve + split panel -----------------------------------------------

function ReservePanel({ data }: { data: CashflowOverviewResponse }) {
  const setTarget = useSetCashflowReserveTarget()
  const forecast = useCashflowForecast(6)
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(String(data.reserve.target))

  const balance = data.reserve.reserve_balance
  const pct = data.reserve.percent_filled ?? 0
  const full = pct >= 100
  const fillMonth = forecast.data?.reserve_fill_month

  function save() {
    const num = parseFloat(value)
    if (!Number.isFinite(num) || num <= 0) return
    setTarget.mutate(num, { onSuccess: () => setEditing(false) })
  }

  return (
    <Panel title="safety reserve" statusDotColor={balance == null ? "muted" : full ? "success" : "warning"}>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          {editing ? (
            <div className="flex items-center gap-2">
              <Input mono className="h-8 w-28" value={value} onChange={(e) => setValue(e.target.value)} placeholder="e.g. 4000" />
              <Button size="sm" onClick={save} disabled={setTarget.isPending}>
                save
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>
                cancel
              </Button>
            </div>
          ) : (
            <>
              <NumberDisplay value={balance} format="currency" emphasized className="text-2xl" />
              <button
                onClick={() => {
                  setValue(String(data.reserve.target))
                  setEditing(true)
                }}
                className="text-xs text-text-label hover:text-accent"
              >
                target {formatCurrency(data.reserve.target)} · set target
              </button>
            </>
          )}
        </div>

        {balance == null ? (
          <EmptyState message="no reserve balance recorded yet — set it from the Reserve & Allocation tab." />
        ) : (
          <>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-border">
              <div
                className={cn("h-full rounded-full transition-[width]", full ? "bg-success" : "bg-accent")}
                style={{ width: `${Math.min(100, pct)}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-text-label">
              <span>{pct}% filled</span>
              <span>{full ? "fully funded" : `${formatCurrency(data.reserve.remaining_to_target ?? 0)} remaining`}</span>
            </div>
            {!full && fillMonth && (
              <div className="text-xs text-text-label">
                projected full by{" "}
                <span className="text-text-secondary">
                  {new Date(`${fillMonth}-01`).toLocaleString("en-US", { month: "long", year: "numeric" })}
                </span>{" "}
                at current pace
              </div>
            )}
          </>
        )}

        <div className="border-t border-border pt-3">
          <div className="label mb-1.5">this month's recommended split</div>
          {data.investable_surplus <= 0 ? (
            <p className="text-xs text-text-label">no investable income yet</p>
          ) : (
            <p className="text-sm text-text-secondary">
              {formatCurrency(data.split_recommendation.to_reserve)} to reserve ·{" "}
              {formatCurrency(data.split_recommendation.to_invest)} to invest
            </p>
          )}
        </div>
      </div>
    </Panel>
  )
}

// --- Top categories + biggest mover ---------------------------------------

// One accent hue family (blue/sky tints) — no categorical "rainbow".
const CAT_COLOR: Record<string, string> = {
  Rent: "bg-blue-600",
  Shopping: "bg-blue-800",
  Restaurants: "bg-sky-400",
  Dining: "bg-sky-400",
  Transport: "bg-blue-500",
  Travel: "bg-sky-500",
  Entertainment: "bg-sky-700",
  Groceries: "bg-blue-400",
  Subscriptions: "bg-blue-300",
  Utilities: "bg-sky-300",
  Health: "bg-sky-600",
}

function CategoryBar({ cat, max }: { cat: CashflowTopCategory; max: number }) {
  const pct = max > 0 ? Math.round((cat.amount / max) * 100) : 0
  const color = CAT_COLOR[cat.category] ?? "bg-text-label"
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-24 shrink-0 text-text-secondary truncate">{cat.category}</span>
      <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-16 text-right tabular-nums text-text-secondary shrink-0">{formatCurrency(cat.amount)}</span>
      <span className="w-9 text-right tabular-nums text-text-label shrink-0">{Math.round(cat.percent_of_total)}%</span>
    </div>
  )
}

function TopCategoriesPanel({ data }: { data: CashflowOverviewResponse }) {
  const topCategories = data.top_categories ?? []
  const max = topCategories[0]?.amount ?? 0
  return (
    <Panel title="top spending this month" statusDotColor="accent">
      {topCategories.length === 0 ? (
        <EmptyState message="no expenses recorded this month." />
      ) : (
        <div className="space-y-3">
          <div className="space-y-1.5">
            {topCategories.map((c) => (
              <CategoryBar key={c.category} cat={c} max={max} />
            ))}
          </div>
          {data.biggest_mover && (
            <p className="rounded-sm border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-text-secondary">
              biggest mover: <span className="font-medium text-warning">{data.biggest_mover.category}</span>{" "}
              {formatPercent(data.biggest_mover.delta_percent, 1)} vs 3-mo avg
            </p>
          )}
        </div>
      )}
    </Panel>
  )
}
