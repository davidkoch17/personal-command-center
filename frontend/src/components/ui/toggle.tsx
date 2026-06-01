import { cn } from "@/lib/utils"

interface ToggleProps<T extends string> {
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
  disabled?: boolean
}

/** Segmented multi-state toggle (e.g. auto / on / off for info-barrier). */
export function Toggle<T extends string>({
  value,
  options,
  onChange,
  disabled = false,
}: ToggleProps<T>) {
  return (
    <div className="inline-flex rounded border border-border bg-bg-panel p-0.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          disabled={disabled}
          onClick={() => onChange(opt.value)}
          className={cn(
            "rounded-sm px-3 py-1 text-xs lowercase transition-colors disabled:opacity-50",
            value === opt.value
              ? "bg-accent text-bg"
              : "text-text-secondary hover:text-text",
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
