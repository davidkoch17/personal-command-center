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
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { AXIS_PROPS, CHART_COLORS, CHART_SERIES, GRID_PROPS } from "./theme"
import { CockpitTooltip } from "./cockpit-tooltip"

const LEGEND_STYLE = {
  fontSize: 11,
  fontFamily: "JetBrains Mono, monospace",
  color: CHART_COLORS.axis,
}

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
        <XAxis dataKey="month" {...AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={48} />
        <Tooltip content={<CockpitTooltip />} cursor={{ fill: "#161C25" }} />
        <Legend wrapperStyle={LEGEND_STYLE} />
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

// --- Category donut ---------------------------------------------------------
export function CategoryDonut({
  data,
  height = 260,
}: {
  data: { name: string; value: number }[]
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
          stroke="#0A0E13"
        >
          {data.map((_, i) => (
            <Cell key={i} fill={CHART_SERIES[i % CHART_SERIES.length]} />
          ))}
        </Pie>
        <Tooltip content={<CockpitTooltip />} />
        <Legend wrapperStyle={LEGEND_STYLE} />
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
        <XAxis type="number" {...AXIS_PROPS} />
        <YAxis type="category" dataKey="type" {...AXIS_PROPS} width={90} />
        <Tooltip content={<CockpitTooltip />} cursor={{ fill: "#161C25" }} />
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
        <XAxis dataKey="Month" {...AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={56} />
        <Tooltip content={<CockpitTooltip />} />
        <Legend wrapperStyle={LEGEND_STYLE} />
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
        <XAxis dataKey="month" {...AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={64} domain={["auto", "auto"]} />
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
        <XAxis dataKey="Month" {...AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={48} />
        <Tooltip content={<CockpitTooltip />} />
        <Legend wrapperStyle={LEGEND_STYLE} />
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
