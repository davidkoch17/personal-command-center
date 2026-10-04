import {
  Area,
  AreaChart,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { AXIS_PROPS, CATEGORY_AXIS_PROPS, CHART_COLORS, CHART_SERIES, formatEuroSigned, formatEuroTick, GRID_PROPS } from "./theme"
import { CockpitTooltip } from "./cockpit-tooltip"
import { CockpitLegend } from "./cockpit-legend"

// --- Income vs expenses (+ savings line) ------------------------------------
export function IncomeExpenseBar({
  data,
}: {
  data: { month: string; income: number; expenses: number }[]
}) {
  const withSavings = data.map((d) => ({ ...d, savings: d.income - d.expenses }))
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={withSavings} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="month" {...CATEGORY_AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={48} tickFormatter={formatEuroTick} />
        <Tooltip content={<CockpitTooltip />} cursor={{ fill: "rgb(var(--color-bg-panel-hover))" }} />
        <Legend content={<CockpitLegend />} />
        <Bar dataKey="income" name="income" fill={CHART_COLORS.success} radius={[2, 2, 0, 0]} />
        <Bar dataKey="expenses" name="expenses" fill={CHART_COLORS.danger} radius={[2, 2, 0, 0]} />
        <Line
          type="monotone"
          dataKey="savings"
          name="net savings"
          stroke={CHART_COLORS.accent}
          strokeWidth={2}
          dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

// --- Income vs expenses vs net (net as its own diverging bar) ---------------
export function IncomeExpenseNetBar({
  data,
}: {
  data: { month: string; income: number; expenses: number; savings: number }[]
}) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="month" {...CATEGORY_AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={48} tickFormatter={formatEuroTick} />
        <Tooltip content={<CockpitTooltip />} cursor={{ fill: "rgb(var(--color-bg-panel-hover))" }} />
        <Legend content={<CockpitLegend />} />
        <Bar dataKey="income" name="income" fill={CHART_COLORS.success} radius={[2, 2, 0, 0]} />
        <Bar dataKey="expenses" name="expenses" fill={CHART_COLORS.danger} radius={[2, 2, 0, 0]} />
        <Bar dataKey="savings" name="net" radius={[2, 2, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.savings >= 0 ? CHART_COLORS.accent : "#93C5FD"} />
          ))}
        </Bar>
      </ComposedChart>
    </ResponsiveContainer>
  )
}

// --- Category donut ---------------------------------------------------------
export function CategoryDonut({
  data,
  height = 260,
}: {
  /** `color` is optional per-item — when a caller has a fixed semantic palette
   * (e.g. BUCKET_COLORS so a bucket's donut slice matches its own legend
   * dot elsewhere), pass it; omitted items fall back to the sequential
   * CHART_SERIES ramp, same as before. */
  data: { name: string; value: number; color?: string }[]
  height?: number
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          innerRadius="55%"
          outerRadius="80%"
          paddingAngle={2}
          stroke="rgb(var(--color-bg))"
        >
          {data.map((d, i) => (
            <Cell key={i} fill={d.color ?? CHART_SERIES[i % CHART_SERIES.length]} />
          ))}
        </Pie>
        <Tooltip content={<CockpitTooltip />} />
        <Legend content={<CockpitLegend />} />
      </PieChart>
    </ResponsiveContainer>
  )
}

// --- Allocation by type (horizontal bars) -----------------------------------
export function AllocationBar({
  data,
}: {
  data: { type: string; value: number }[]
}) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(120, data.length * 44)}>
      <ComposedChart
        layout="vertical"
        data={data}
        margin={{ top: 4, right: 16, bottom: 4, left: 8 }}
      >
        <CartesianGrid {...GRID_PROPS} horizontal={false} vertical />
        <XAxis type="number" {...AXIS_PROPS} tickFormatter={formatEuroTick} />
        <YAxis type="category" dataKey="type" {...CATEGORY_AXIS_PROPS} width={90} />
        <Tooltip content={<CockpitTooltip />} cursor={{ fill: "rgb(var(--color-bg-panel-hover))" }} />
        <Bar dataKey="value" name="value" fill={CHART_COLORS.accent} radius={[0, 2, 2, 0]} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

// --- Portfolio value over time (stacked area: TR + Crypto) ------------------
export function PerformanceArea({
  data,
  series,
}: {
  data: Record<string, string | number | null>[]
  series: { key: string; color: string }[]
}) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="Month" {...CATEGORY_AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={56} tickFormatter={formatEuroTick} />
        <Tooltip content={<CockpitTooltip />} />
        <Legend content={<CockpitLegend />} />
        {series.map((s) => (
          <Area
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.key}
            stackId="1"
            stroke={s.color}
            fill={s.color}
            fillOpacity={0.18}
            strokeWidth={2}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  )
}

// --- Net-worth over time (N1) — single accent line ---------------------------
export function NetWorthTrendLine({
  data,
  height = 240,
}: {
  data: { month: string; total: number | null }[]
  height?: number
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <defs>
          <linearGradient id="nwFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART_COLORS.accent} stopOpacity={0.25} />
            <stop offset="100%" stopColor={CHART_COLORS.accent} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="month" {...CATEGORY_AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={64} domain={["auto", "auto"]} tickFormatter={formatEuroTick} />
        <Tooltip content={<CockpitTooltip />} />
        <Area
          type="monotone"
          dataKey="total"
          name="net worth"
          stroke={CHART_COLORS.accent}
          strokeWidth={2}
          fill="url(#nwFill)"
          dot={false}
          connectNulls
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

// --- Forecast: projected reserve balance vs. target (F8) ---------------------
export function ReserveTrajectoryLine({
  data,
  target,
}: {
  data: { month: string; projected_reserve_balance: number }[]
  target: number
}) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <defs>
          <linearGradient id="reserveTrajectoryFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART_COLORS.success} stopOpacity={0.22} />
            <stop offset="100%" stopColor={CHART_COLORS.success} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="month" {...CATEGORY_AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={56} tickFormatter={formatEuroTick} />
        <Tooltip content={<CockpitTooltip />} />
        <ReferenceLine
          y={target}
          ifOverflow="extendDomain"
          stroke={CHART_COLORS.axis}
          strokeDasharray="4 4"
          label={{ value: `target ${formatEuroTick(target)}`, position: "insideTopRight", fill: CHART_COLORS.axis, fontSize: 11 }}
        />
        <Area
          type="monotone"
          dataKey="projected_reserve_balance"
          name="reserve balance"
          stroke={CHART_COLORS.success}
          strokeWidth={2}
          fill="url(#reserveTrajectoryFill)"
          dot={{ r: 3 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

// --- Forecast: monthly surplus split, reserve vs. invest (F8) ---------------
export function ReserveInvestSplitBar({
  data,
}: {
  data: { month: string; to_reserve: number; to_invest: number }[]
}) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="month" {...CATEGORY_AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={48} tickFormatter={formatEuroTick} />
        <Tooltip content={<CockpitTooltip />} cursor={{ fill: "rgb(var(--color-bg-panel-hover))" }} />
        <Legend content={<CockpitLegend />} />
        <Bar dataKey="to_reserve" name="to reserve" stackId="split" fill={CHART_COLORS.success} />
        <Bar dataKey="to_invest" name="to invest" stackId="split" fill={CHART_COLORS.invest} radius={[2, 2, 0, 0]} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

// --- Savings rate + income stability trend (F8) -------------------------------
export function SavingsIncomeStabilityTrend({
  data,
}: {
  data: { month: string; savings_rate: number | null; income_stability: number | null }[]
}) {
  const pct = data.map((d) => ({
    month: d.month,
    "savings rate": d.savings_rate != null ? Math.round(d.savings_rate * 1000) / 10 : null,
    "income stability": d.income_stability != null ? Math.round(d.income_stability * 1000) / 10 : null,
  }))
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={pct} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="month" {...CATEGORY_AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={48} tickFormatter={(v: number) => `${v}%`} />
        <Tooltip content={<CockpitTooltip valueFormatter={(v: number) => `${v}%`} />} />
        <Legend content={<CockpitLegend />} />
        <Line type="monotone" dataKey="savings rate" stroke={CHART_COLORS.accent} strokeWidth={2} dot={false} connectNulls />
        <Line type="monotone" dataKey="income stability" stroke={CHART_COLORS.invest} strokeWidth={2} dot={false} connectNulls />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

// --- Category monthly trend (multi-line) ------------------------------------
export function CategoryTrendLine({
  data,
  categories,
}: {
  data: Record<string, string | number | null>[]
  categories: string[]
}) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="Month" {...CATEGORY_AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={48} tickFormatter={formatEuroTick} />
        <Tooltip content={<CockpitTooltip />} />
        <Legend content={<CockpitLegend />} />
        {categories.map((c, i) => (
          <Line
            key={c}
            type="monotone"
            dataKey={c}
            name={c}
            stroke={CHART_SERIES[i % CHART_SERIES.length]}
            strokeWidth={1.5}
            dot={false}
          />
        ))}
      </ComposedChart>
    </ResponsiveContainer>
  )
}

// --- Monthly net-worth bridge waterfall (N9) ---------------------------------
export interface BridgeStep {
  label: string
  amount: number
  /** Opening/closing bars stand on their own (from zero), not stacked on the running total. */
  isTotal?: boolean
}

interface BridgeBar {
  name: string
  base: number
  size: number
  display: number
  kind: "total" | "up" | "down"
}

function buildBridgeBars(steps: BridgeStep[]): BridgeBar[] {
  let running = 0
  return steps.map((s) => {
    if (s.isTotal) {
      running = s.amount
      return { name: s.label, base: 0, size: s.amount, display: s.amount, kind: "total" as const }
    }
    const start = running
    running = start + s.amount
    return {
      name: s.label,
      base: Math.min(start, running),
      size: Math.abs(s.amount),
      display: s.amount,
      kind: s.amount >= 0 ? ("up" as const) : ("down" as const),
    }
  })
}

function bridgeBarColor(kind: BridgeBar["kind"]): string {
  if (kind === "total") return CHART_COLORS.accent
  return kind === "up" ? CHART_COLORS.success : CHART_COLORS.danger
}

function BridgeTooltip({ active, payload }: { active?: boolean; payload?: { payload: BridgeBar }[] }) {
  const point = payload?.[0]?.payload
  if (!active || !point) return null
  return (
    <div className="rounded-sm border border-border bg-bg-panel px-2.5 py-1.5 shadow-md">
      <div className="mb-1 font-mono text-xs text-text-secondary">{point.name}</div>
      <div className="font-mono text-xs tabular-nums text-text">{formatEuroSigned(point.display, 2)}</div>
    </div>
  )
}

/** Floating-bar waterfall: each step's bar sits on an invisible offset ("base")
 *  stacked with the visible delta ("size"), so intermediate bars float between
 *  the running total instead of starting from zero — opening/closing are full
 *  bars from zero (`isTotal`). */
export function NetWorthBridgeWaterfall({ steps }: { steps: BridgeStep[] }) {
  const data = buildBridgeBars(steps)
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="name" {...CATEGORY_AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={64} tickFormatter={formatEuroTick} domain={["auto", "auto"]} />
        <Tooltip content={<BridgeTooltip />} cursor={{ fill: "rgb(var(--color-bg-panel-hover))" }} />
        <Bar dataKey="base" stackId="bridge" fill="transparent" isAnimationActive={false} />
        <Bar dataKey="size" stackId="bridge" radius={[2, 2, 2, 2]}>
          {data.map((d, i) => (
            <Cell key={i} fill={bridgeBarColor(d.kind)} />
          ))}
        </Bar>
      </ComposedChart>
    </ResponsiveContainer>
  )
}
