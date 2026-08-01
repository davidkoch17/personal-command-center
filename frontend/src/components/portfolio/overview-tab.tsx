import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { MetricPanel } from "@/components/finance/metric-panel"
import { NumberDisplay } from "@/components/ui/number-display"
import { DecisionAlerts } from "@/components/finance/decision-alerts"
import { AXIS_PROPS, CHART_COLORS, GRID_PROPS } from "@/components/charts/theme"
import { CockpitTooltip } from "@/components/charts/cockpit-tooltip"
import {
  useMoneySnapshot,
  useMoneyAvailableMonths,
  useMoneyAllocation,
  useNetWorthHistory,
} from "@/hooks/useFinance"
import { useNetWorthDaily, useNetWorthDecomposition } from "@/hooks/usePortfolioHub"
import { formatCurrency } from "@/lib/utils"

export function OverviewTab() {
  const snap = useMoneySnapshot()
  const daily = useNetWorthDaily(90)
  const nwHistory = useNetWorthHistory()
  const months = useMoneyAvailableMonths()
  const latestMonth = months.data?.months.at(-1) ?? null
  const alloc = useMoneyAllocation(latestMonth)

  // Excel is the net-worth source of truth app-wide (see money.latest_net_worth()
  // docstring) — the live-ledger-priced daily/decomposition endpoints below are
  // chart/analytics only and must never supply the headline figure.
  const netWorth = snap.data?.net_worth ?? null
  const history = nwHistory.data?.history ?? []
  const lastMonth = history.at(-1)
  const prevMonth = history.at(-2)
  const mom =
    lastMonth?.total != null && prevMonth?.total != null
      ? Math.round((lastMonth.total - prevMonth.total) * 100) / 100
      : null
  const runway = snap.data?.runway_months ?? null
  const reserve = alloc.data?.reserve
  const notgroschenPct = reserve?.percent_filled ?? null

  return (
    <div className="space-y-5">
      {/* KPI band */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricPanel
          label="net worth"
          value={
            snap.isLoading ? (
              <Skeleton className="h-7 w-32" />
            ) : (
              <NumberDisplay value={netWorth} format="currency" emphasized animate />
            )
          }
          caption={
            snap.data?.net_worth_breakdown?.month
              ? `excel · as of ${snap.data.net_worth_breakdown.month}`
              : "excel"
          }
        />
        <MetricPanel
          label="this month (Δ net worth)"
          dotColor={mom == null ? "muted" : mom >= 0 ? "success" : "danger"}
          value={
            nwHistory.isLoading ? (
              <Skeleton className="h-7 w-24" />
            ) : (
              <NumberDisplay value={mom} format="currency" signed />
            )
          }
          caption={mom != null && lastMonth ? `excel · ${lastMonth.month}` : "excel · not enough history"}
        />
        <MetricPanel
          label="runway"
          dotColor={runway == null ? "muted" : runway >= 6 ? "success" : runway >= 3 ? "warning" : "danger"}
          value={
            snap.isLoading ? (
              <Skeleton className="h-7 w-20" />
            ) : runway == null ? (
              <span className="text-text-label">—</span>
            ) : (
              <span className="font-mono font-medium tabular-nums">{runway.toFixed(1)} mo</span>
            )
          }
          caption="cash ÷ fixed burn"
        />
        <MetricPanel
          label="notgroschen"
          dotColor={notgroschenPct == null ? "muted" : notgroschenPct >= 100 ? "success" : "warning"}
          value={
            alloc.isLoading ? (
              <Skeleton className="h-7 w-20" />
            ) : notgroschenPct == null ? (
              <span className="text-text-label">—</span>
            ) : (
              <span className="font-mono font-medium tabular-nums">{notgroschenPct}%</span>
            )
          }
          caption={
            reserve?.reserve_balance == null
              ? `not recorded yet · target ${formatCurrency(reserve?.target ?? null)}`
              : `${formatCurrency(reserve.reserve_balance)} of ${formatCurrency(reserve.target)} buffer`
          }
        />
      </div>

      {/* 90-day net-worth sparkline — live-ledger-priced chart trend, NOT the
          Excel-sourced headline above; the two can legitimately differ. */}
      <Panel
        title="net worth — last 90 days"
        meta={daily.data ? `${daily.data.count} snapshots (live-priced trend)` : undefined}
        statusDotColor="accent"
      >
        {daily.isLoading ? (
          <Skeleton className="h-48" />
        ) : !daily.data?.series.length ? (
          <EmptyState message="no daily snapshots yet — the 18:00 job seeds this." />
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={daily.data.series} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
              <defs>
                <linearGradient id="nwHubFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CHART_COLORS.accent} stopOpacity={0.25} />
                  <stop offset="100%" stopColor={CHART_COLORS.accent} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid {...GRID_PROPS} />
              <XAxis dataKey="date" {...AXIS_PROPS} minTickGap={32} />
              <YAxis {...AXIS_PROPS} width={64} domain={["auto", "auto"]} />
              <Tooltip content={<CockpitTooltip />} />
              <Area
                type="monotone"
                dataKey="net_worth_eur"
                name="net worth"
                stroke={CHART_COLORS.accent}
                strokeWidth={2}
                fill="url(#nwHubFill)"
                dot={false}
                connectNulls
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Panel>

      {/* This-month decomposition */}
      <ThisMonthDecomposition />

      {/* Portfolio decision-alerts strip */}
      <DecisionAlerts />
    </div>
  )
}

function ThisMonthDecomposition() {
  const { data, isLoading } = useNetWorthDecomposition()

  return (
    <Panel
      title="this month — what drove it"
      meta={data?.month ?? undefined}
      statusDotColor="accent"
    >
      {isLoading ? (
        <Skeleton className="h-24" />
      ) : !data?.available ? (
        <EmptyState message={data?.reason ?? "not enough history yet"} />
      ) : (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <DriverCard
              label="savings (cash flow)"
              value={data.savings ?? null}
              hint={data.savings_source === "income_vs_expenses" ? "income − expenses" : "derived"}
            />
            <DriverCard
              label="investments (market p&l)"
              value={data.investments ?? null}
              hint="price-driven, contributions netted"
            />
            <DriverCard
              label="Δ net worth (live-priced)"
              value={data.mom_delta ?? null}
              hint="savings + investments"
              emphasized
            />
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-label">
            <span>
              net contributions (depot, net-worth-neutral):{" "}
              <NumberDisplay value={data.net_contributions ?? null} format="currency" signed className="text-text-secondary" />
            </span>
            {data.residual != null && Math.abs(data.residual) >= 1 && (
              <span>
                unreconciled (bank timing):{" "}
                <NumberDisplay value={data.residual} format="currency" signed className="text-text-secondary" />
              </span>
            )}
          </div>
          <p className="text-xs text-text-label">
            this breakdown is priced off the live daily ledger, not the Excel headline above — the
            two are expected to diverge (see the "net worth" KPI for the authoritative figure).
          </p>
        </div>
      )}
    </Panel>
  )
}

function DriverCard({
  label,
  value,
  hint,
  emphasized,
}: {
  label: string
  value: number | null
  hint: string
  emphasized?: boolean
}) {
  return (
    <div className="rounded-sm border border-border bg-bg-panel px-3 py-2">
      <div className="label mb-1">{label}</div>
      <div className="text-xl">
        <NumberDisplay value={value} format="currency" signed={!emphasized} emphasized={emphasized} />
      </div>
      <div className="mt-0.5 text-xs text-text-label">{hint}</div>
    </div>
  )
}

