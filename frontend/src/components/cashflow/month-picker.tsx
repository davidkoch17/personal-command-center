/** Prev/next month stepper shared across the Cash Flow pillar's per-month tabs. */
export function MonthPicker({
  months,
  month,
  onChange,
}: {
  months: string[]
  month: string | null
  onChange: (month: string) => void
}) {
  const idx = month ? months.indexOf(month) : -1
  const canPrev = idx > 0
  const canNext = idx >= 0 && idx < months.length - 1
  const label = month
    ? new Date(month + "-01").toLocaleString("en-US", { month: "long", year: "numeric" })
    : "—"

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => canPrev && onChange(months[idx - 1])}
        disabled={!canPrev}
        className="rounded px-1.5 py-0.5 text-xs text-text-label hover:text-text-secondary disabled:opacity-30 transition-colors"
      >
        ←
      </button>
      <span className="font-mono text-xs text-text-secondary tabular-nums min-w-[110px] text-center">
        {label}
      </span>
      <button
        onClick={() => canNext && onChange(months[idx + 1])}
        disabled={!canNext}
        className="rounded px-1.5 py-0.5 text-xs text-text-label hover:text-text-secondary disabled:opacity-30 transition-colors"
      >
        →
      </button>
    </div>
  )
}
