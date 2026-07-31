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
  grid: "rgb(var(--color-border))",
  axis: "rgb(var(--color-text-label))",
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

export const GRID_PROPS = {
  stroke: CHART_COLORS.grid,
  strokeDasharray: "0",
  vertical: false,
} as const
