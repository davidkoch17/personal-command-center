import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  LabelList,
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
import { AXIS_PROPS, CHART_COLORS, FACTOR_COLORS, GRID_PROPS } from "./theme"

import { cn } from "@/lib/utils"

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

// --- Single-stock price line (Single Stock tab, Chunk 4) --------------------
// Same conventions as IndexedPerformanceChart (invest violet, no dots, shared
// grid/axis/tooltip styling) for one series in the instrument's native currency.
export function PriceSparkline({
  data,
  currency,
}: {
  data: { date: string; close: number }[]
  currency?: string | null
}) {
  const fmt = (v: number) => `${currency ? `${currency} ` : ""}${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
  // Long ranges: one tick per month ("25-10"), thinned to <= 8; a single month
  // label repeated every few days (the default) reads as noise. Short ranges: MM-DD.
  const long = data.length > 130
  let ticks: string[] | undefined
  if (long) {
    const firsts = data.filter((p, i) => i === 0 || p.date.slice(0, 7) !== data[i - 1].date.slice(0, 7)).map((p) => p.date)
    const step = Math.ceil(firsts.length / 8)
    ticks = firsts.filter((_, i) => i % step === 0)
  }
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="date" {...AXIS_PROPS} ticks={ticks} tickFormatter={(d: string) => (long ? d.slice(2, 7) : d.slice(5))} minTickGap={40} />
        <YAxis {...AXIS_PROPS} width={52} domain={["auto", "auto"]} tickFormatter={(v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 })} />
        <Tooltip
          contentStyle={{ background: "rgb(var(--color-bg-panel))", border: `1px solid ${CHART_COLORS.grid}`, fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}
          formatter={(v: number) => fmt(v)}
          labelStyle={{ color: CHART_COLORS.axis }}
        />
        <Line type="monotone" dataKey="close" name="close" stroke={CHART_COLORS.invest} strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

// --- N benchmarks indexed to 100 (Benchmarks tab, Chunk 5) ------------------
// A sibling of IndexedPerformanceChart rather than an extension of it: that one is
// hard-wired to "portfolio vs one benchmark" (fixed keys, dashed overlay), and
// generalizing it would risk the Portfolio tab it already serves. Same axis / grid /
// tooltip conventions; the first series is drawn heavier as the primary reference.
export function BenchmarkComparisonChart({
  data,
  series,
}: {
  data: Record<string, string | number>[]
  series: { key: string; name: string; color: string }[]
}) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="date" {...AXIS_PROPS} tickFormatter={shortDate} minTickGap={48} />
        <YAxis {...AXIS_PROPS} width={44} domain={["auto", "auto"]} />
        <Tooltip
          contentStyle={{ background: "rgb(var(--color-bg-panel))", border: `1px solid ${CHART_COLORS.grid}`, fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}
          formatter={(v: number) => v.toFixed(2)}
          labelStyle={{ color: CHART_COLORS.axis }}
        />
        <Legend verticalAlign="top" align="left" wrapperStyle={{ ...LEGEND_STYLE, paddingBottom: 8 }} />
        <ReferenceLine y={100} stroke={CHART_COLORS.axis} strokeDasharray="2 2" />
        {series.map((s, i) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.name}
            stroke={s.color}
            strokeWidth={i === 0 ? 2.5 : 1.5}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

// --- Security Market Line (workspace Performance tab, Chunk 6) -----------------
// x = beta, y = return. The CAPM line is drawn as a ReferenceLine `segment` (same
// trick as the CML on the frontier chart); each holding is a point coloured by the
// sign of its alpha — above the line = success, below = danger — and the portfolio
// roll-up is the violet diamond. Hover shows ticker, beta, actual return and alpha.
interface SmlChartPoint {
  ticker: string
  beta: number
  expected_return_capm: number
  actual_return: number
  alpha: number
}

function SmlTooltip({ active, payload }: { active?: boolean; payload?: { payload: SmlChartPoint }[] }) {
  const p = active && payload?.length ? payload[0].payload : null
  if (!p) return null
  const pc = (v: number) => `${(v * 100).toFixed(1)}%`
  return (
    <div
      className="rounded-sm border px-2 py-1.5"
      style={{ background: "rgb(var(--color-bg-panel))", borderColor: CHART_COLORS.grid, fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}
    >
      <div style={{ color: CHART_COLORS.axis }}>{p.ticker}</div>
      <div>β {p.beta.toFixed(2)}</div>
      <div>actual {pc(p.actual_return)}</div>
      <div>capm {pc(p.expected_return_capm)}</div>
      <div style={{ color: p.alpha >= 0 ? CHART_COLORS.success : CHART_COLORS.danger }}>
        alpha {p.alpha >= 0 ? "+" : ""}{pc(p.alpha)}
      </div>
    </div>
  )
}

export function SecurityMarketLineChart({
  line,
  points,
  portfolio,
  market,
}: {
  line: { intercept: number; slope: number }
  points: SmlChartPoint[]
  portfolio?: SmlChartPoint | null
  market?: { beta: number; expected_return: number } | null
}) {
  const xMax = Math.max(2, Math.ceil((Math.max(1, ...points.map((p) => p.beta), portfolio?.beta ?? 0) + 0.2) * 2) / 2)
  const segment = [
    { x: 0, y: line.intercept },
    { x: xMax, y: line.intercept + line.slope * xMax },
  ]
  // A holding that *is* the benchmark has alpha of exactly zero up to float noise (~1e-17);
  // treat |alpha| < 0.01pp as "on the line" (neutral/above) rather than colouring it red.
  const above = points.filter((p) => p.alpha >= -1e-4)
  const below = points.filter((p) => p.alpha < -1e-4)
  const xTicks = Array.from({ length: Math.floor(xMax / 0.5) + 1 }, (_, i) => i * 0.5)
  const label = { dataKey: "ticker", position: "top" as const, fontSize: 10, fill: CHART_COLORS.axis }

  return (
    <ResponsiveContainer width="100%" height={340}>
      <ScatterChart margin={{ top: 12, right: 24, bottom: 20, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} vertical />
        <XAxis
          type="number"
          dataKey="beta"
          name="beta"
          domain={[0, xMax]}
          ticks={xTicks}
          {...AXIS_PROPS}
          tickFormatter={(v: number) => v.toFixed(1)}
          label={{ value: "beta (β)", position: "insideBottom", offset: -8, fill: CHART_COLORS.axis, fontSize: 11 }}
        />
        <YAxis type="number" dataKey="actual_return" name="return" domain={["auto", "auto"]} {...AXIS_PROPS} width={48} tickFormatter={pctTick} />
        <ZAxis range={[70, 70]} />
        <Tooltip content={<SmlTooltip />} cursor={{ strokeDasharray: "3 3", stroke: CHART_COLORS.grid }} />
        <ReferenceLine y={0} stroke={CHART_COLORS.axis} strokeOpacity={0.4} />
        <ReferenceLine
          segment={segment}
          stroke={CHART_COLORS.cml}
          strokeWidth={2}
          ifOverflow="extendDomain"
          label={{ value: "SML", position: "insideTopRight", fill: CHART_COLORS.cml, fontSize: 11 }}
        />
        {market && (
          <Scatter
            name="market"
            data={[{ ticker: "market", beta: market.beta, actual_return: market.expected_return, expected_return_capm: market.expected_return, alpha: 0 }]}
            fill={CHART_COLORS.accent}
            shape="circle"
            isAnimationActive={false}
          />
        )}
        <Scatter name="above the line" data={above} fill={CHART_COLORS.success} isAnimationActive={false}>
          <LabelList {...label} />
        </Scatter>
        <Scatter name="below the line" data={below} fill={CHART_COLORS.danger} isAnimationActive={false}>
          <LabelList {...label} />
        </Scatter>
        {portfolio && (
          <Scatter name="portfolio" data={[portfolio]} fill={CHART_COLORS.invest} shape="diamond" isAnimationActive={false}>
            <LabelList {...label} />
          </Scatter>
        )}
      </ScatterChart>
    </ResponsiveContainer>
  )
}

// --- Rolling factor betas (Factors tab, Chunk 8) ----------------------------------------
export function RollingFactorBetasChart({
  dates,
  series,
}: {
  dates: string[]
  series: Record<string, number[]>
}) {
  const keys = Object.keys(series)
  const data = dates.map((d, i) => ({ date: d, ...Object.fromEntries(keys.map((k) => [k, series[k][i]])) }))
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="date" {...AXIS_PROPS} tickFormatter={(d: string) => d.slice(2)} minTickGap={48} />
        <YAxis {...AXIS_PROPS} width={40} tickFormatter={(v: number) => v.toFixed(1)} />
        <Tooltip
          contentStyle={{ background: "rgb(var(--color-bg-panel))", border: `1px solid ${CHART_COLORS.grid}`, fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}
          formatter={(v: number, name: string) => [v.toFixed(2), `β ${name}`]}
          labelStyle={{ color: CHART_COLORS.axis }}
        />
        <Legend verticalAlign="top" align="left" wrapperStyle={{ ...LEGEND_STYLE, paddingBottom: 8 }} formatter={(v: string) => `β ${v}`} />
        <ReferenceLine y={0} stroke={CHART_COLORS.axis} strokeDasharray="2 2" />
        {keys.map((k) => (
          <Line key={k} type="monotone" dataKey={k} name={k.toUpperCase()} stroke={FACTOR_COLORS[k] ?? CHART_COLORS.axis}
            strokeWidth={k === "mkt" ? 2.25 : 1.75} dot={false} isAnimationActive={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

// --- Portfolio vs benchmark factor loadings (Chunk 8) -----------------------------------
// Two series per factor: the portfolio solid, the comparison benchmark hatched/muted.
export function FactorLoadingsComparisonChart({
  data,
  benchmarkName,
}: {
  data: { factor: string; portfolio: number; benchmark: number }[]
  benchmarkName: string
}) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }} barGap={4}>
        <defs>
          <pattern id="bench-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="rgb(var(--color-bg-panel))" />
            <line x1="0" y1="0" x2="0" y2="6" stroke={CHART_COLORS.axis} strokeWidth="3" />
          </pattern>
        </defs>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="factor" {...AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={40} tickFormatter={(v: number) => v.toFixed(1)} />
        <Tooltip
          contentStyle={{ background: "rgb(var(--color-bg-panel))", border: `1px solid ${CHART_COLORS.grid}`, fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}
          formatter={(v: number) => v.toFixed(2)}
          cursor={{ fill: "rgba(148,163,184,0.12)" }}
        />
        <Legend verticalAlign="top" align="left" wrapperStyle={{ ...LEGEND_STYLE, paddingBottom: 8 }} />
        <ReferenceLine y={0} stroke={CHART_COLORS.axis} />
        <Bar dataKey="portfolio" name="portfolio" fill={CHART_COLORS.accent} radius={[2, 2, 0, 0]} isAnimationActive={false} />
        <Bar dataKey="benchmark" name={benchmarkName} fill="url(#bench-hatch)" stroke={CHART_COLORS.axis} strokeWidth={1} radius={[2, 2, 0, 0]} isAnimationActive={false} />
      </BarChart>
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

/** Neutral slate → invest violet as correlation rises 0 → 1 (negatives clamp to
 *  neutral). No green/red — used by the Benchmarks tab (Chunk 5). */
function investCorrColor(v: number): string {
  const t = Math.max(0, Math.min(1, v))
  const from = [71, 85, 105]
  const to = [139, 92, 246]
  return `rgb(${from.map((f, i) => Math.round(f + t * (to[i] - f))).join(", ")})`
}

export function CorrelationHeatmap({
  tickers,
  matrix,
  scale = "diverging",
  size = "sm",
  italicTickers,
}: {
  tickers: string[]
  matrix: Record<string, string | number>[]
  /** "diverging" (default, Risk tab): blue ↔ red. "invest": neutral → violet. */
  scale?: "diverging" | "invest"
  /** "lg" = roomy cells for small (e.g. 4×4) matrices. */
  size?: "sm" | "lg"
  /** Labels rendered in italics (the Risk tab marks the comparison benchmarks this way). */
  italicTickers?: string[]
}) {
  const italic = new Set(italicTickers ?? [])
  const wideLabels = italic.size > 0
  const color = scale === "invest" ? investCorrColor : corrColor
  const large = size === "lg"
  if (tickers.length === 0) return <p className="text-sm text-text-label">no correlation data</p>
  const byTicker = new Map(matrix.map((r) => [String(r.ticker), r]))
  return (
    <div className="overflow-x-auto">
      <table className="border-separate border-spacing-0.5">
        <thead>
          <tr>
            <th className={wideLabels ? "" : large ? "w-28" : "w-14"} />
            {tickers.map((t) => (
              <th key={t} className={cn(large ? "px-2 py-1.5 font-mono text-xs text-text-secondary" : "px-1.5 py-1 font-mono text-[10px] text-text-secondary", italic.has(t) && "italic")}>
                {t}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tickers.map((row) => (
            <tr key={row}>
              <td className={cn(large ? "pr-3 text-right font-mono text-xs text-text-secondary" : "pr-2 text-right font-mono text-[10px] text-text-secondary", italic.has(row) && "italic", wideLabels && "whitespace-nowrap")}>{row}</td>
              {tickers.map((col) => {
                const v = Number(byTicker.get(row)?.[col] ?? 0)
                return (
                  <td
                    key={col}
                    className={large ? "h-14 w-28 text-center font-mono text-sm text-white/95" : "h-9 w-12 text-center font-mono text-[10px] text-white/90"}
                    style={{ backgroundColor: color(v) }}
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
