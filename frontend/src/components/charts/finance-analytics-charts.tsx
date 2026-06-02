import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { AXIS_PROPS, CHART_COLORS, GRID_PROPS } from "./theme"

const LEGEND_STYLE = {
  fontSize: 11,
  fontFamily: "JetBrains Mono, monospace",
  color: CHART_COLORS.axis,
}

const pctTick = (v: number) => `${(v * 100).toFixed(0)}%`
const shortDate = (d: string) => (d.length >= 7 ? d.slice(2, 7) : d)

// --- Cumulative return: portfolio vs benchmark ------------------------------
export function CumulativeReturnChart({
  data,
  benchmarkName = "benchmark",
}: {
  data: { date: string; portfolio: number; benchmark: number }[]
  benchmarkName?: string
}) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="date" {...AXIS_PROPS} tickFormatter={shortDate} minTickGap={40} />
        <YAxis {...AXIS_PROPS} width={48} tickFormatter={pctTick} />
        <Tooltip
          contentStyle={{ background: "#0A0E13", border: `1px solid ${CHART_COLORS.grid}`, fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}
          formatter={(v: number) => `${(v * 100).toFixed(2)}%`}
          labelStyle={{ color: CHART_COLORS.axis }}
        />
        <Legend wrapperStyle={LEGEND_STYLE} />
        <ReferenceLine y={0} stroke={CHART_COLORS.axis} strokeDasharray="2 2" />
        <Line type="monotone" dataKey="portfolio" name="portfolio" stroke={CHART_COLORS.accent} strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="benchmark" name={benchmarkName} stroke={CHART_COLORS.warning} strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
      </LineChart>
    </ResponsiveContainer>
  )
}

// --- Rolling Sharpe ---------------------------------------------------------
export function RollingSharpeChart({
  data,
}: {
  data: { date: string; sharpe: number | null }[]
}) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="date" {...AXIS_PROPS} tickFormatter={shortDate} minTickGap={40} />
        <YAxis {...AXIS_PROPS} width={40} />
        <Tooltip
          contentStyle={{ background: "#0A0E13", border: `1px solid ${CHART_COLORS.grid}`, fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}
          formatter={(v: number) => v?.toFixed(2)}
          labelStyle={{ color: CHART_COLORS.axis }}
        />
        <ReferenceLine y={0} stroke={CHART_COLORS.axis} strokeDasharray="2 2" />
        <ReferenceLine y={1} stroke={CHART_COLORS.success} strokeDasharray="2 2" />
        <Line type="monotone" dataKey="sharpe" name="rolling sharpe" stroke={CHART_COLORS.accent} strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

// --- Best / worst period bars -----------------------------------------------
export function BestWorstBars({
  data,
}: {
  data: { label: string; return: number }[]
}) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, data.length * 40)}>
      <BarChart layout="vertical" data={data} margin={{ top: 4, right: 24, bottom: 4, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} horizontal={false} vertical />
        <XAxis type="number" {...AXIS_PROPS} tickFormatter={pctTick} />
        <YAxis type="category" dataKey="label" {...AXIS_PROPS} width={88} />
        <Tooltip
          contentStyle={{ background: "#0A0E13", border: `1px solid ${CHART_COLORS.grid}`, fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}
          formatter={(v: number) => `${(v * 100).toFixed(2)}%`}
          cursor={{ fill: "#161C25" }}
        />
        <ReferenceLine x={0} stroke={CHART_COLORS.axis} />
        <Bar dataKey="return" name="return" radius={[0, 2, 2, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.return >= 0 ? CHART_COLORS.success : CHART_COLORS.danger} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

// --- Correlation heatmap (custom grid) --------------------------------------
/** Blue (low) → red (high) cell color for a correlation in [-1, 1]. */
function corrColor(v: number): string {
  // Map -1..1 to a diverging scale: negative = teal, ~0 = slate, positive = warm.
  if (v >= 0) {
    const t = Math.min(1, v)
    const r = Math.round(37 + t * (239 - 37))
    const g = Math.round(99 + t * (68 - 99))
    const b = Math.round(235 + t * (68 - 235))
    return `rgb(${r}, ${g}, ${b})`
  }
  const t = Math.min(1, -v)
  return `rgb(${Math.round(37 - t * 17)}, ${Math.round(99 + t * 85)}, ${Math.round(235 - t * 65)})`
}

export function CorrelationHeatmap({
  tickers,
  matrix,
}: {
  tickers: string[]
  matrix: Record<string, string | number>[]
}) {
  if (tickers.length === 0) return <p className="text-sm text-text-label">no correlation data</p>
  const byTicker = new Map(matrix.map((r) => [String(r.ticker), r]))
  return (
    <div className="overflow-x-auto">
      <table className="border-separate border-spacing-0.5">
        <thead>
          <tr>
            <th className="w-14" />
            {tickers.map((t) => (
              <th key={t} className="px-1.5 py-1 font-mono text-[10px] text-text-secondary">
                {t}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tickers.map((row) => (
            <tr key={row}>
              <td className="pr-2 text-right font-mono text-[10px] text-text-secondary">{row}</td>
              {tickers.map((col) => {
                const v = Number(byTicker.get(row)?.[col] ?? 0)
                return (
                  <td
                    key={col}
                    className="h-9 w-12 text-center font-mono text-[10px] text-white/90"
                    style={{ backgroundColor: corrColor(v) }}
                    title={`${row} · ${col}: ${v.toFixed(2)}`}
                  >
                    {v.toFixed(2)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
