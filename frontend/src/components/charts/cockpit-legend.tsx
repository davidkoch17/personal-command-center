interface LegendEntry {
  value?: string
  color?: string
}

/** Cockpit-styled Recharts legend: small square swatches, monospace labels —
 *  consistent regardless of the underlying series shape (bar, line, area). */
export function CockpitLegend({ payload }: { payload?: LegendEntry[] }) {
  if (!payload || payload.length === 0) return null
  return (
    <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-1.5 font-mono text-[11px] text-text-label">
          <span className="h-2.5 w-2.5 shrink-0 rounded-[2px]" style={{ background: entry.color }} />
          <span>{entry.value}</span>
        </div>
      ))}
    </div>
  )
}
