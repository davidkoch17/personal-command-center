import type { TooltipProps } from "recharts"
import { formatEuroSigned } from "./theme"

interface CockpitTooltipProps extends TooltipProps<number, string> {
  /** Override the value formatter — defaults to German-formatted euros with
   *  the sign before the symbol (`−€1.498`). Pass e.g. a percent formatter
   *  for non-currency series. */
  valueFormatter?: (value: number) => string
}

/** Cockpit-styled Recharts tooltip: bordered panel, monospace values, square
 *  swatches (matches the legend), German-formatted euros by default. */
export function CockpitTooltip({
  active,
  payload,
  label,
  valueFormatter = formatEuroSigned,
}: CockpitTooltipProps) {
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
              className="h-2.5 w-2.5 shrink-0 rounded-[2px]"
              style={{ background: entry.color }}
            />
            <span className="text-text-secondary">{entry.name}</span>
            <span className="ml-auto font-mono text-text tabular-nums">
              {typeof entry.value === "number" ? valueFormatter(entry.value) : entry.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
