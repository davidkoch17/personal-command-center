import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { AXIS_PROPS, CHART_COLORS, CHART_SERIES, GRID_PROPS } from "@/components/charts/theme"
import { CockpitTooltip } from "@/components/charts/cockpit-tooltip"
import type { LifePlanResult, MilestoneKey, YearRow } from "@/hooks/useLifeplan"
import { axisShort, eur } from "./format"
import { MILESTONE_LABELS } from "./drivers-panel"

const LEGEND_STYLE = { fontSize: 11, color: CHART_COLORS.axis }
const fmtEur = (v: number) => eur(v)

const MILESTONE_SHORT: Record<MilestoneKey, string> = {
  main_car: "Main Car",
  fun_car: "Oldtimer",
  house_munich: "Grünwald",
  sports_car: "Sportwagen",
  house_cape: "Kapstadt",
}

/** Net worth + liquid wealth over age, target line, purchases, warning years. */
export function WealthChart({ result, height = 360 }: { result: LifePlanResult; height?: number }) {
  const data = result.years.map((y) => ({ age: y.age, net: y.net_worth, liquid: y.liquid }))
  const warnings = result.years.filter((y) => y.warning)
  const purchases = result.years.filter((y) => y.purchased.length > 0)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 22, right: 12, left: 4, bottom: 0 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="age" type="number" domain={["dataMin", "dataMax"]} allowDecimals={false} {...AXIS_PROPS} tickCount={11} />
        <YAxis tickFormatter={axisShort} width={64} {...AXIS_PROPS} />
        {warnings.map((y) => (
          <ReferenceArea key={`w${y.age}`} x1={y.age - 0.5} x2={y.age + 0.5} fill={CHART_COLORS.danger} fillOpacity={0.08} strokeOpacity={0} ifOverflow="hidden" />
        ))}
        <ReferenceLine y={0} stroke={CHART_COLORS.axis} strokeOpacity={0.5} />
        <ReferenceLine
          y={result.summary.target}
          stroke={CHART_COLORS.success}
          strokeDasharray="6 4"
          ifOverflow="extendDomain"
          label={{ value: `Ziel ${axisShort(result.summary.target)}`, position: "insideTopLeft", fill: CHART_COLORS.success, fontSize: 11 }}
        />
        {purchases.map((y, i) => (
          <ReferenceLine
            key={`p${y.age}`}
            x={y.age}
            stroke={CHART_COLORS.warning}
            strokeDasharray="2 3"
            label={{
              value: y.purchased.map((k) => MILESTONE_SHORT[k]).join(" + "),
              // alternate above / inside so neighbouring purchases don't overlap
              position: i % 2 === 0 ? "top" : "insideTopRight",
              fill: CHART_COLORS.warning,
              fontSize: 10,
            }}
          />
        ))}
        <Tooltip content={<CockpitTooltip valueFormatter={fmtEur} />} labelFormatter={(a) => `Alter ${a}`} />
        <Legend wrapperStyle={LEGEND_STYLE} />
        <Line type="monotone" dataKey="net" name="Nettovermögen" stroke={CHART_COLORS.accent} strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line type="monotone" dataKey="liquid" name="Liquides Vermögen" stroke={CHART_SERIES[4]} strokeWidth={2} dot={false} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

const FLOW_SERIES: { key: string; name: string; color: string; get: (y: YearRow) => number }[] = [
  { key: "taxes", name: "Steuern/Abgaben", color: "#77756D", get: (y) => y.social + y.partner_social + y.income_tax + y.soli_church },
  { key: "lifestyle", name: "Lifestyle", color: "#1F3D42", get: (y) => y.lifestyle + y.buffer },
  { key: "rent", name: "Miete", color: "#4A7C80", get: (y) => y.rent },
  { key: "kids", name: "Kinder", color: "#9DBDBE", get: (y) => y.kids },
  { key: "insurance", name: "Versicherungen", color: "#A8A49B", get: (y) => y.insurance },
  { key: "homes", name: "Häuser & Autos", color: "#B07E62", get: (y) => y.homes_cars },
  { key: "loan", name: "Kreditrate", color: "#7A3B48", get: (y) => y.loan_payment },
  { key: "savings", name: "Sparen", color: "#3F7A5C", get: (y) => y.savings },
]

/** Stacked bars: where each year's gross income goes. */
export function FlowsChart({ result }: { result: LifePlanResult }) {
  const data = result.years.map((y) => {
    const row: Record<string, number> = { age: y.age }
    for (const s of FLOW_SERIES) row[s.key] = s.get(y)
    return row
  })
  return (
    <ResponsiveContainer width="100%" height={380}>
      <BarChart data={data} stackOffset="sign" margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="age" {...AXIS_PROPS} interval={1} />
        <YAxis tickFormatter={axisShort} width={64} {...AXIS_PROPS} />
        <Tooltip content={<CockpitTooltip valueFormatter={fmtEur} />} labelFormatter={(a) => `Alter ${a}`} />
        <Legend wrapperStyle={LEGEND_STYLE} />
        <ReferenceLine y={0} stroke={CHART_COLORS.axis} />
        {FLOW_SERIES.map((s) => (
          <Bar key={s.key} dataKey={s.key} name={s.name} stackId="a" fill={s.color} isAnimationActive={false} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Gross salary vs household net over age. */
export function CareerChart({ result }: { result: LifePlanResult }) {
  const data = result.years.map((y) => ({
    age: y.age,
    gross: y.salary,
    partner: y.partner_gross,
    net: y.net_income,
  }))
  return (
    <ResponsiveContainer width="100%" height={340}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="age" {...AXIS_PROPS} interval={2} />
        <YAxis tickFormatter={axisShort} width={64} {...AXIS_PROPS} />
        <Tooltip content={<CockpitTooltip valueFormatter={fmtEur} />} labelFormatter={(a) => `Alter ${a}`} />
        <Legend wrapperStyle={LEGEND_STYLE} />
        <Line type="stepAfter" dataKey="gross" name="Gehalt brutto (du)" stroke={CHART_COLORS.accent} strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line type="stepAfter" dataKey="partner" name="Partnerin brutto" stroke={CHART_SERIES[4]} strokeWidth={1.5} dot={false} isAnimationActive={false} />
        <Line type="stepAfter" dataKey="net" name="Netto Haushalt" stroke={CHART_COLORS.success} strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export const COMPARE_COLORS = [CHART_COLORS.accent, "#B07E62", CHART_COLORS.invest]

/** Net worth of up to 3 scenarios over age. */
export function CompareChart({ series }: { series: { name: string; result: LifePlanResult }[] }) {
  const ages = series[0]?.result.years.map((y) => y.age) ?? []
  const data = ages.map((age, i) => {
    const row: Record<string, number> = { age }
    series.forEach((s, j) => {
      row[`s${j}`] = s.result.years[i]?.net_worth ?? NaN
    })
    return row
  })
  return (
    <ResponsiveContainer width="100%" height={340}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="age" {...AXIS_PROPS} interval={2} />
        <YAxis tickFormatter={axisShort} width={64} {...AXIS_PROPS} />
        <Tooltip content={<CockpitTooltip valueFormatter={fmtEur} />} labelFormatter={(a) => `Alter ${a}`} />
        <Legend wrapperStyle={LEGEND_STYLE} />
        {series.map((s, j) => (
          <Line key={j} type="monotone" dataKey={`s${j}`} name={s.name} stroke={COMPARE_COLORS[j]} strokeWidth={2} dot={false} isAnimationActive={false} />
        ))}
        {series.map((s, j) => (
          <ReferenceLine key={`t${j}`} y={s.result.summary.target} stroke={COMPARE_COLORS[j]} strokeDasharray="6 4" strokeOpacity={0.6} ifOverflow="extendDomain" />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

export { MILESTONE_LABELS }
