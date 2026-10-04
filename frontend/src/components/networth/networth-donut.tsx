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

      <ul className="w-full max-w-sm space-y-1.5 lg:max-w-[260px]">
        {segments.map((s) => (
          <li key={s.name} className="flex items-center justify-between gap-2 text-sm">
            <span className="flex items-center gap-2 text-text-secondary">
              <span className="h-2.5 w-2.5 shrink-0 rounded-[2px]" style={{ background: s.color }} />
              {s.name}
            </span>
            <span className="font-mono tabular-nums text-text">
              {((s.value / total) * 100).toFixed(1)}% · {formatCurrency(s.value)}
            </span>
          </li>
        ))}
        {hasLiability && (
          <li className="flex items-center justify-between gap-2 text-sm">
            <span className="flex items-center gap-2 text-text-secondary">
              <span className="h-2.5 w-2.5 shrink-0 rounded-[2px]" style={{ background: CHART_COLORS.danger }} />
              Liabilities
            </span>
            <span className="font-mono tabular-nums text-danger">
              −{formatCurrency(breakdown.liabilities)}
            </span>
          </li>
        )}
      </ul>
    </div>
  )
}
