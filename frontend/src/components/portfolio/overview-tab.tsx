import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { MetricPanel } from "@/components/finance/metric-panel"
import { NumberDisplay } from "@/components/ui/number-display"
import { DecisionAlerts } from "@/components/finance/decision-alerts"
import { AXIS_PROPS, CHART_COLORS, GRID_PROPS } from "@/components/charts/theme"
import { CockpitTooltip } from "@/components/charts/cockpit-tooltip"
import { useMoneySnapshot } from "@/hooks/useFinance"
import { useNetWorthDaily, useNetWorthDecomposition } from "@/hooks/usePortfolioHub"
import { formatCurrency } from "@/lib/utils"

// Notgroschen (emergency buffer) Phase-1 target — see wealth_config Mehrkontenmodell.
const NOTGROSCHEN_TARGET = 4000

export function OverviewTab() {
  const snap = useMoneySnapshot()
  const daily = useNetWorthDaily(90)
  const decomp = useNetWorthDecomposition()

  const netWorth = decomp.data?.net_worth_now ?? snap.data?.net_worth ?? null
  const mom = decomp.data?.mom_delta ?? null
  const cash = snap.data?.cash_balance ?? null
  const runway = snap.data?.runway_months ?? null
  const notgroschenPct =
    cash != null ? Math.min(100, Math.round((cash / NOTGROSCHEN_TARGET) * 100)) : null

  return (
    <div className="space-y-5">
      {/* KPI band */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricPanel
          label="net worth"
          value={
            decomp.isLoading && snap.isLoading ? (
              <Skeleton className="h-7 w-32" />
            ) : (
              <NumberDisplay value={netWorth} format="currency" emphasized animate />
            )
          }
          caption={decomp.data?.as_of ? `as of ${decomp.data.as_of}` : "live"}
        />
        <MetricPanel
          label="this month (Δ net worth)"
          dotColor={mom == null ? "muted" : mom >= 0 ? "success" : "danger"}
          value={
            decomp.isLoading ? (
              <Skeleton className="h-7 w-24" />
            ) : (
              <NumberDisplay value={mom} format="currency" signed />
            )
          }
          caption={decomp.data?.month ?? undefined}
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
            snap.isLoading ? (
              <Skeleton className="h-7 w-20" />
            ) : notgroschenPct == null ? (
              <span className="text-text-label">—</span>
            ) : (
              <span className="font-mono font-medium tabular-nums">{notgroschenPct}%</span>
            )
          }
          caption={`${formatCurrency(cash)} of ${formatCurrency(NOTGROSCHEN_TARGET)} buffer`}
        />
      </div>

      {/* 90-day net-worth sparkline */}
      <Panel
        title="net worth — last 90 days"
        meta={daily.data ? `${daily.data.count} snapshots` : undefined}
        statusDotColor="accent"
      >
        {daily.isLoading ? (
          <Skeleton className="h-48" />
        ) : !daily.data?.series.length ? (
          <p className="text-sm text-text-label">no daily snapshots yet — the 18:00 job seeds this.</p>
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
        <p className="text-sm text-text-label">{data?.reason ?? "not enough history yet"}</p>
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
              label="Δ net worth"
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
