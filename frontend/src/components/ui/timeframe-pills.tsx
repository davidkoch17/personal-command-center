import { cn } from "@/lib/utils"

/**
 * Timeframe pill row (1M / 3M / … ) — same look the Portfolio tab (Chunk 2) and
 * Single Stock tab (Chunk 4) render inline. Extracted here for the Benchmarks tab;
 * those two keep their existing inline copies untouched (they're a follow-up
 * migration, not part of this change).
 */
export function TimeframePills<K extends string>({
  options,
  value,
  onChange,
  className,
}: {
  options: readonly { key: K; label: string }[]
  value: K
  onChange: (key: K) => void
  className?: string
}) {
  return (
    <div className={cn("flex flex-wrap gap-1.5", className)}>
      {options.map((o) => (
        <button
          key={o.key}
          type="button"
          onClick={() => onChange(o.key)}
          className={cn(
            "rounded-sm border px-3 py-1 font-mono text-xs transition-colors",
            value === o.key
              ? "border-accent text-accent bg-bg-panel-hover"
              : "border-border text-text-secondary hover:text-text",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
