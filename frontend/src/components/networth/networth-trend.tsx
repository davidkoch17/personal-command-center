import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { TimeframePills } from "@/components/ui/timeframe-pills"
import { EmptyState } from "@/components/ui/empty-state"
import { AXIS_PROPS, CATEGORY_AXIS_PROPS, CHART_COLORS, formatEuroTick, GRID_PROPS } from "@/components/charts/theme"
import { CockpitTooltip } from "@/components/charts/cockpit-tooltip"
import { TrendingUp } from "lucide-react"
import type { NetworthPeriod, NetworthTrend } from "@/hooks/useNetworth"

const TIMEFRAMES: { key: NetworthPeriod; label: string }[] = [
  { key: "1M", label: "1M" },
  { key: "3M", label: "3M" },
  { key: "YTD", label: "YTD" },
  { key: "1Y", label: "1Y" },
  { key: "ALL", label: "ALL" },
]

/** Section 2 — net-worth trend sparkline with timeframe pills (default 3M,
 * set by the parent page so switching periods re-fetches the bundled snapshot). */
export function NetworthTrendChart({
  trend,
  period,
  onPeriodChange,
}: {
  trend: NetworthTrend
  period: NetworthPeriod
  onPeriodChange: (p: NetworthPeriod) => void
}) {
  return (
    <div className="space-y-3">
      <TimeframePills options={TIMEFRAMES} value={period} onChange={onPeriodChange} />
      {!trend.available ? (
        <EmptyState icon={TrendingUp} message="building trend history — check back in a few days" />
      ) : trend.series.length < 2 ? (
        <EmptyState icon={TrendingUp} message="building trend history — check back in a few days" />
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={trend.series} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
            <CartesianGrid {...GRID_PROPS} />
            <XAxis dataKey="date" {...CATEGORY_AXIS_PROPS} interval="preserveStartEnd" />
            <YAxis {...AXIS_PROPS} width={56} tickFormatter={formatEuroTick} domain={["auto", "auto"]} />
            <Tooltip content={<CockpitTooltip />} />
            <Line
              type="monotone"
              dataKey="net_worth_eur"
              name="net worth"
              stroke={CHART_COLORS.invest}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
