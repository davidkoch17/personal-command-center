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
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
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
          contentStyle={{ background: "rgb(var(--color-bg-panel))", border: `1px solid ${CHART_COLORS.grid}`, fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}
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

// --- Indexed performance: portfolio vs benchmark, both rebased to 100 -------
// (Portfolio tab, Chunk 2) — same shape as CumulativeReturnChart but the Y axis
// is a plain index value (100 = start of period) rather than a % return, and
// the benchmark line is dashed/muted per the spec (overlay, not a peer series).
export function IndexedPerformanceChart({
  data,
  benchmarkName = "benchmark",
}: {
  data: { date: string; portfolio: number; benchmark: number }[]
  benchmarkName?: string
}) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="date" {...AXIS_PROPS} tickFormatter={shortDate} minTickGap={40} />
        <YAxis {...AXIS_PROPS} width={44} domain={["auto", "auto"]} />
        <Tooltip
          contentStyle={{ background: "rgb(var(--color-bg-panel))", border: `1px solid ${CHART_COLORS.grid}`, fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}
          formatter={(v: number) => v.toFixed(2)}
          labelStyle={{ color: CHART_COLORS.axis }}
        />
        <Legend wrapperStyle={LEGEND_STYLE} />
        <ReferenceLine y={100} stroke={CHART_COLORS.axis} strokeDasharray="2 2" />
        <Line type="monotone" dataKey="portfolio" name="portfolio" stroke={CHART_COLORS.invest} strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="benchmark" name={benchmarkName} stroke={CHART_COLORS.axis} strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
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
          contentStyle={{ background: "rgb(var(--color-bg-panel))", border: `1px solid ${CHART_COLORS.grid}`, fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}
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
          contentStyle={{ background: "rgb(var(--color-bg-panel))", border: `1px solid ${CHART_COLORS.grid}`, fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}
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

// --- Efficient frontier scatter ---------------------------------------------
// Chunk 3: optional CML (B1, drawn via a ReferenceLine `segment` — the only
// way Recharts draws an arbitrary diagonal line rather than an axis-aligned
// one) and an optional constrained-frontier overlay (D8's Preview). When
// `constrained` is supplied the unconstrained curve/markers "ghost" (muted,
// dashed, lower opacity) and the constrained ones take the full-color/solid
// styling instead — the current-portfolio marker (✕) is never ghosted either
// way, it's the one fixed reference point across both views.
export function EfficientFrontierScatter({
  frontier,
  current,
  maxSharpe,
  minVariance,
  riskFreeRate,
  constrained,
}: {
  frontier: { risk: number; return: number }[]
  current?: { risk: number; return: number } | null
  maxSharpe?: { risk: number; return: number } | null
  minVariance?: { risk: number; return: number } | null
  /** B1 — draws the CML from (0, riskFreeRate) through the tangency point. */
  riskFreeRate?: number | null
  /** D8 preview overlay — when present, the props above render ghosted. */
  constrained?: {
    points: { risk: number; return: number }[]
    tangency?: { risk: number; return: number } | null
    minVariance?: { risk: number; return: number } | null
  } | null
}) {
  const tip = {
    contentStyle: {
      background: "rgb(var(--color-bg-panel))",
      border: `1px solid ${CHART_COLORS.grid}`,
      fontFamily: "JetBrains Mono, monospace",
      fontSize: 11,
    },
    formatter: (v: number) => `${(v * 100).toFixed(1)}%`,
    labelStyle: { color: CHART_COLORS.axis },
  }

  const hasOverlay = !!constrained
  const baseOpacity = hasOverlay ? 0.55 : 1

  // CML: straight line from (0, rfr) through the tangency point, extended
  // past it — at least 1.5x the tangency vol, and past the frontier's own
  // rightmost point too, so it reads as reaching the chart's edge regardless
  // of which extent is larger.
  const cmlSegment =
    riskFreeRate != null && maxSharpe
      ? (() => {
          const slope = (maxSharpe.return - riskFreeRate) / maxSharpe.risk
          const maxFrontierRisk = frontier.reduce((m, p) => Math.max(m, p.risk), maxSharpe.risk)
          const endX = Math.max(maxSharpe.risk * 1.5, maxFrontierRisk * 1.1)
          return [
            { x: 0, y: riskFreeRate },
            { x: endX, y: riskFreeRate + slope * endX },
          ]
        })()
      : null

  return (
    <ResponsiveContainer width="100%" height={340}>
      <ScatterChart margin={{ top: 8, right: 16, bottom: 16, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} vertical />
        <XAxis
          type="number"
          dataKey="risk"
          name="risk"
          {...AXIS_PROPS}
          tickFormatter={pctTick}
          label={{ value: "risk (vol)", position: "insideBottom", offset: -8, fill: CHART_COLORS.axis, fontSize: 11 }}
        />
        <YAxis
          type="number"
          dataKey="return"
          name="return"
          {...AXIS_PROPS}
          width={48}
          tickFormatter={pctTick}
        />
        <ZAxis range={[40, 40]} />
        <Tooltip {...tip} cursor={{ strokeDasharray: "3 3", stroke: CHART_COLORS.grid }} />
        <Legend wrapperStyle={LEGEND_STYLE} />

        {cmlSegment && (
          <ReferenceLine
            segment={cmlSegment}
            stroke={CHART_COLORS.cml}
            strokeWidth={2}
            ifOverflow="extendDomain"
            label={{ value: "CML", position: "insideTopRight", fill: CHART_COLORS.cml, fontSize: 11 }}
          />
        )}

        <Scatter
          name={hasOverlay ? "frontier (unconstrained)" : "frontier"}
          data={frontier}
          fill={CHART_COLORS.axis}
          fillOpacity={baseOpacity}
          line={{ stroke: CHART_COLORS.axis, strokeWidth: 1.5, strokeDasharray: hasOverlay ? "4 3" : undefined, strokeOpacity: baseOpacity }}
          shape="circle"
          opacity={baseOpacity}
        />
        {minVariance && (
          <Scatter name={hasOverlay ? "min variance (unconstrained)" : "min variance"} data={[minVariance]} fill={CHART_COLORS.success} shape="diamond" opacity={baseOpacity} />
        )}
        {maxSharpe && (
          <Scatter name={hasOverlay ? "max sharpe (unconstrained)" : "max sharpe"} data={[maxSharpe]} fill={CHART_COLORS.warning} shape="star" opacity={baseOpacity} />
        )}
        {current && (
          <Scatter name="current" data={[current]} fill={CHART_COLORS.danger} shape="cross" />
        )}

        {hasOverlay && constrained!.points.length > 0 && (
          <Scatter
            name="frontier (constrained)"
            data={constrained!.points}
            fill={CHART_COLORS.accent}
            line={{ stroke: CHART_COLORS.accent, strokeWidth: 2.5 }}
            shape="circle"
          />
        )}
        {hasOverlay && constrained!.minVariance && (
          <Scatter name="min variance (constrained)" data={[constrained!.minVariance]} fill={CHART_COLORS.success} shape="diamond" />
        )}
        {hasOverlay && constrained!.tangency && (
          <Scatter name="max sharpe (constrained)" data={[constrained!.tangency]} fill={CHART_COLORS.warning} shape="star" />
        )}
      </ScatterChart>
    </ResponsiveContainer>
  )
}

// --- Factor beta bars (FF3 exposures) ---------------------------------------
export function FactorBetaBars({
  data,
}: {
  data: { factor: string; beta: number }[]
}) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="factor" {...AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={40} />
        <Tooltip
          contentStyle={{ background: "rgb(var(--color-bg-panel))", border: `1px solid ${CHART_COLORS.grid}`, fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}
          formatter={(v: number) => v.toFixed(2)}
          cursor={{ fill: "#161C25" }}
        />
        <ReferenceLine y={0} stroke={CHART_COLORS.axis} />
        <Bar dataKey="beta" name="beta" radius={[2, 2, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.beta >= 0 ? CHART_COLORS.accent : CHART_COLORS.danger} />
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
