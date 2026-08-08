/**
 * Cash Flow design conventions (Phase 0). Single reference point for every
 * later Cash Flow phase — don't restate these choices in component code,
 * import from here or from the modules re-exported below.
 *
 * Theme: polished light theme, matching the rest of the app (see globals.css
 * `.light` palette). Numbers: German locale everywhere — €1.838,09 (dot
 * thousands, comma decimal) — via `formatCurrency` / `formatNumber` /
 * `formatPercent` in `@/lib/utils`.
 *
 * Fixed color meanings (`MONEY_COLORS` below) — never reuse these hues for
 * anything unrelated to their meaning:
 *   income = success (green) · expenses = danger (red) · net = accent (blue)
 *   reserve = success (green) · investments = invest (violet)
 *
 * Chart style (Recharts, see `@/components/charts/theme`):
 *   - no vertical gridlines, light horizontal gridlines only (`GRID_PROPS`)
 *   - category axes show every tick, never auto-skip (`CATEGORY_AXIS_PROPS`)
 *   - value axes use compact euro ticks, e.g. "€2k" (`formatEuroTick`)
 *   - legend: small square swatches, not the series' native shape
 *     (`CockpitLegend` in `@/components/charts/cockpit-legend`)
 *   - tooltips: German-formatted euros, sign before the symbol, e.g. "−€1.498"
 *     (`CockpitTooltip` in `@/components/charts/cockpit-tooltip`, defaults to
 *     `formatEuroSigned`)
 *
 * Typography & spacing: tabular figures for all money (`font-mono
 * tabular-nums`, already the default in `NumberDisplay`); lowercase `.label`
 * class for panel titles/section labels; KPI headline figures at `text-2xl`,
 * chip-level figures at `text-base` (see `MetricPanel`, the KPI chips in
 * `overview-tab.tsx`).
 *
 * Layout: sections stack vertically (`space-y-4` on the tab root); small
 * items (KPI cards, account chips) sit in a row within their section via
 * `grid grid-cols-2 sm:grid-cols-4 gap-3`, never forced full-width.
 *
 * States: `EmptyState` for "no data yet", `Skeleton` for loading — both in
 * `@/components/ui`. Reuse them; don't invent ad hoc placeholder text.
 *
 * Reuse Panel / MetricPanel / NumberDisplay / KpiChip / CategoryBar — don't
 * introduce a parallel UI kit.
 */
export { formatCurrency, formatNumber, formatPercent } from "@/lib/utils"
export {
  CATEGORY_AXIS_PROPS,
  AXIS_PROPS as VALUE_AXIS_PROPS,
  GRID_PROPS,
  CHART_COLORS,
  MONEY_COLORS,
  formatEuroTick,
  formatEuroSigned,
} from "@/components/charts/theme"
export { CockpitTooltip } from "@/components/charts/cockpit-tooltip"
export { CockpitLegend } from "@/components/charts/cockpit-legend"
