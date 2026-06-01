import type { TooltipProps } from "recharts"

/** Cockpit-styled Recharts tooltip: bordered panel, monospace values. */
export function CockpitTooltip({
  active,
  payload,
  label,
}: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null
  return (
    <div className="rounded-sm border border-border bg-bg-panel px-2.5 py-1.5 shadow-md">
      {label != null && (
        <div className="mb-1 font-mono text-xs text-text-secondary">{label}</div>
      )}
      <div className="space-y-0.5">
        {payload.map((entry, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: entry.color }}
            />
            <span className="text-text-secondary">{entry.name}</span>
            <span className="ml-auto font-mono text-text">
              {typeof entry.value === "number"
                ? entry.value.toLocaleString("en-US", { maximumFractionDigits: 2 })
                : entry.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
