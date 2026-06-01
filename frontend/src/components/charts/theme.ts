/** Cockpit chart palette + shared axis/grid styling for Recharts. */
export const CHART_COLORS = {
  accent: "#2563EB",
  success: "#10B981",
  danger: "#EF4444",
  warning: "#F59E0B",
  grid: "#1F262E",
  axis: "#8A929E",
} as const

/** A small categorical ramp (accent-led) for donuts / multi-series charts. */
export const CHART_SERIES = [
  "#2563EB",
  "#10B981",
  "#F59E0B",
  "#8A929E",
  "#1D4ED8",
  "#6366F1",
  "#14B8A6",
  "#EF4444",
  "#A855F7",
  "#5C6470",
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
