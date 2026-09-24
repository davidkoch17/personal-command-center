/**
 * Cockpit chart palette + shared axis/grid styling for Recharts. Grid/axis
 * reference the same theme variables as everything else (rgb(var(--x))
 * resolves at paint time) so charts stay correct across light/dark instead of
 * being tuned for one theme only.
 */
export const CHART_COLORS = {
  accent: "#2563EB",
  success: "#10B981",
  danger: "#EF4444",
  warning: "#F59E0B",
  invest: "#8B5CF6",
  // Capital Market Line (Chunk 3 B1) — distinct from accent (frontier curve)
  // and invest (portfolio-tracking violet elsewhere); reads clearly in both
  // themes without being mistaken for a status color (success/danger/warning).
  cml: "#06B6D4",
  grid: "rgb(var(--color-border))",
  axis: "rgb(var(--color-text-label))",
} as const

/**
 * Fixed color meanings — reuse everywhere, never repurpose for anything else:
 * income = success (green), expenses = danger (red), net = accent (blue),
 * reserve = success (green), investments = invest (violet, its own accent
 * distinct from `accent`/net-blue).
 */
export const MONEY_COLORS = {
  income: CHART_COLORS.success,
  expenses: CHART_COLORS.danger,
  net: CHART_COLORS.accent,
  reserve: CHART_COLORS.success,
  investments: CHART_COLORS.invest,
} as const

/** One accent hue family, light→dark tints — no more categorical "rainbow". */
export const CHART_SERIES = [
  "#2563EB",
  "#3B82F6",
  "#60A5FA",
  "#1D4ED8",
  "#93C5FD",
  "#0EA5E9",
  "#1E40AF",
  "#7DD3FC",
  "#0369A1",
  "#BFDBFE",
] as const

export const AXIS_PROPS = {
  stroke: CHART_COLORS.axis,
  tick: { fill: CHART_COLORS.axis, fontSize: 11, fontFamily: "JetBrains Mono, monospace" },
  tickLine: false,
} as const

/** Category axis (months, labels) — always show every tick, never auto-skip. */
export const CATEGORY_AXIS_PROPS = {
  ...AXIS_PROPS,
  interval: 0,
} as const

export const GRID_PROPS = {
  stroke: CHART_COLORS.grid,
  strokeDasharray: "0",
  vertical: false,
} as const

/** Compact euro-formatted axis tick, German locale: `€2.000` → `€2k`. */
export function formatEuroTick(value: number): string {
  const abs = Math.abs(value)
  const sign = value < 0 ? "−" : ""
  if (abs >= 1000) {
    const scaled = abs / 1000
    const formatted = scaled.toLocaleString("de-DE", {
      maximumFractionDigits: scaled < 10 ? 1 : 0,
    })
    return `${sign}€${formatted}k`
  }
  return `${sign}€${abs.toLocaleString("de-DE")}`
}

/** Full German-formatted euro amount, sign before the symbol: `−€1.498`. */
export function formatEuroSigned(value: number, decimals: number = 0): string {
  const sign = value < 0 ? "−" : ""
  const formatted = Math.abs(value).toLocaleString("de-DE", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
  return `${sign}€${formatted}`
}
