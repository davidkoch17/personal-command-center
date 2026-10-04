import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts"
import { CHART_COLORS, NETWORTH_SEGMENT_COLORS } from "@/components/charts/theme"
import { CockpitTooltip } from "@/components/charts/cockpit-tooltip"
import { formatCurrency } from "@/lib/utils"
import { cn } from "@/lib/utils"
import type { NetworthBreakdown } from "@/hooks/useNetworth"

const SEGMENT_DEFS: { key: keyof NetworthBreakdown; label: string }[] = [
  { key: "bank_cash", label: "Bank Cash" },
  { key: "brokerage_cash", label: "Brokerage Cash" },
  { key: "etfs", label: "ETFs" },
  { key: "single_stocks", label: "Single Stocks" },
  { key: "crypto", label: "Crypto" },
  { key: "wild_cards", label: "Wild Cards" },
]

/**
 * Hero donut (Chunk 9.7, Section 1) — asset-class breakdown with the current
 * total centered in the hole. Zero-value segments (Single Stocks, Wild Cards
 * today) are omitted entirely rather than rendered as empty slivers.
 * Colors come from NETWORTH_SEGMENT_COLORS (theme.ts), the same source the
 * Portfolio tab's Allocation-vs-Target donut uses for its bucket slices — so
 * e.g. Crypto is the same amber on both pages, not an arbitrary shade picked
 * by slice order.
 */
export function NetworthDonut({
  breakdown,
  deltaThisMonth,
}: {
  breakdown: NetworthBreakdown
  deltaThisMonth: number | null
}) {
  const segments = SEGMENT_DEFS.map((def) => ({
    name: def.label,
    value: breakdown[def.key] as number,
    color: NETWORTH_SEGMENT_COLORS[def.key],
  })).filter((s) => s.value > 0)

  const total = breakdown.total
  const hasLiability = breakdown.liabilities > 0

  const deltaClass =
    deltaThisMonth == null
      ? "text-text-label"
      : deltaThisMonth > 0
        ? "text-invest"
        : deltaThisMonth < 0
          ? "text-danger"
          : "text-text-label"

  return (
    <div className="flex flex-col items-center gap-6 lg:flex-row lg:justify-center">
      <div className="relative mx-auto aspect-square w-full max-w-[90vw] sm:max-w-[420px] lg:w-[60%] lg:max-w-[480px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={segments}
              dataKey="value"
              nameKey="name"
              innerRadius="62%"
              outerRadius="92%"
              paddingAngle={2}
              stroke="rgb(var(--color-bg))"
            >
              {segments.map((s, i) => (
                <Cell key={i} fill={s.color} />
              ))}
            </Pie>
            <Tooltip content={<CockpitTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        {/* Centered total — an HTML overlay (not SVG text) so it scales and
            wraps cleanly at any viewport without recomputing chart geometry. */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-1 px-4 text-center">
          <span className="font-mono text-[clamp(1.75rem,6vw,3rem)] font-semibold leading-none tabular-nums">
            {formatCurrency(total)}
          </span>
          <span className={cn("font-mono text-sm tabular-nums", deltaClass)}>
            {deltaThisMonth == null
              ? "Δ this month — not enough history"
              : `${deltaThisMonth >= 0 ? "+" : ""}${formatCurrency(deltaThisMonth)} this month`}
          </span>
        </div>
      </div>

      <ul className="w-full max-w-sm space-y-1.5 lg:max-w-[320px]">
        {segments.map((s) => (
          <LegendRow
            key={s.name}
            color={s.color}
            label={s.name}
            pct={`${((s.value / total) * 100).toFixed(1)}%`}
            value={formatCurrency(s.value)}
          />
        ))}
        {hasLiability && (
          <LegendRow
            color={CHART_COLORS.danger}
            label="Liabilities"
            pct=""
            value={`−${formatCurrency(breakdown.liabilities)}`}
            valueClassName="text-danger"
          />
        )}
      </ul>
    </div>
  )
}

/**
 * One legend line. Desktop (≥480px): a 4-column grid (swatch / label / % /
 * €) so every row's numbers line up instead of the label's length pushing
 * the value onto its own wrapped line (the bug this replaces — "Brokerage
 * Cash" + its value no longer fit on one line at the old flex-justify-between
 * layout's width). Below 480px: the two inner wrappers switch from
 * `contents` (dissolving into the grid) to a plain flex row, so the row
 * naturally stacks as label-then-numbers instead of cramming four columns
 * into a narrow screen.
 */
function LegendRow({
  color,
  label,
  pct,
  value,
  valueClassName,
}: {
  color: string
  label: string
  pct: string
  value: string
  valueClassName?: string
}) {
  return (
    <li className="flex flex-wrap items-center gap-x-2 gap-y-0.5 min-[480px]:grid min-[480px]:grid-cols-[12px_1fr_55px_90px] min-[480px]:items-center">
      <div className="flex w-full items-center gap-2 min-[480px]:contents">
        <span className="h-2.5 w-2.5 shrink-0 rounded-[2px]" style={{ background: color }} />
        <span className="min-w-0 flex-1 truncate text-sm text-text-secondary min-[480px]:flex-none">
          {label}
        </span>
      </div>
      <div className="ml-[18px] flex items-center gap-3 min-[480px]:contents">
        <span className="font-mono text-sm tabular-nums text-text min-[480px]:text-right">{pct}</span>
        <span
          className={cn(
            "font-mono text-sm tabular-nums min-[480px]:text-right",
            valueClassName ?? "text-text",
          )}
        >
          {value}
        </span>
      </div>
    </li>
  )
}
