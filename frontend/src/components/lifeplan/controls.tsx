import { useEffect, useState, type ReactNode } from "react"
import { cn } from "@/lib/utils"

/** Kinds of numeric input: the stored value is a fraction for "pct". */
export type NumKind = "eur" | "pct" | "age" | "num"

const LOCALE = "de-DE"

function toDisplay(v: number, kind: NumKind): string {
  if (!Number.isFinite(v)) return ""
  const shown = kind === "pct" ? v * 100 : v
  return shown.toLocaleString(LOCALE, { maximumFractionDigits: kind === "pct" ? 2 : 2, useGrouping: kind === "eur" })
}

function parse(text: string, kind: NumKind): number | null {
  const cleaned = text.replace(/\s|€|%/g, "").replace(/\./g, "").replace(",", ".")
  if (cleaned === "" || cleaned === "-") return null
  const n = Number(cleaned)
  if (!Number.isFinite(n)) return null
  return kind === "pct" ? n / 100 : n
}

const UNIT: Record<NumKind, string> = { eur: "€", pct: "%", age: "J.", num: "" }

/**
 * Compact numeric field with German formatting. Commits on blur / Enter so a
 * half-typed value never triggers a recompute.
 */
export function NumInput({
  value,
  onChange,
  kind = "num",
  className,
  disabled,
  ariaLabel,
}: {
  value: number
  onChange: (v: number) => void
  kind?: NumKind
  className?: string
  disabled?: boolean
  ariaLabel?: string
}) {
  const [text, setText] = useState(toDisplay(value, kind))
  const [focused, setFocused] = useState(false)
  useEffect(() => {
    if (!focused) setText(toDisplay(value, kind))
  }, [value, kind, focused])

  const commit = () => {
    const n = parse(text, kind)
    if (n != null && n !== value) onChange(n)
    else setText(toDisplay(value, kind))
  }

  return (
    <div className={cn("relative", className)}>
      <input
        aria-label={ariaLabel}
        disabled={disabled}
        inputMode="decimal"
        value={text}
        onFocus={() => setFocused(true)}
        onBlur={() => {
          setFocused(false)
          commit()
        }}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur()
        }}
        className={cn(
          "h-8 w-full rounded-sm border border-border bg-bg px-2 pr-7 text-right font-mono text-xs text-text",
          "focus-visible:border-border-focus focus-visible:outline-none disabled:text-text-disabled",
        )}
      />
      {UNIT[kind] && (
        <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-text-label">
          {UNIT[kind]}
        </span>
      )}
    </div>
  )
}

/** Label + number field in one row. */
export function NumField({
  label,
  hint,
  ...props
}: { label: ReactNode; hint?: ReactNode } & Parameters<typeof NumInput>[0]) {
  return (
    <label className="grid grid-cols-[1fr_110px] items-center gap-2 py-0.5">
      <span className="text-xs text-text-secondary">
        {label}
        {hint && <span className="ml-1 text-[10px] text-text-label">{hint}</span>}
      </span>
      <NumInput ariaLabel={typeof label === "string" ? label : undefined} {...props} />
    </label>
  )
}

/** Label + range slider + exact field. */
export function SliderField({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  kind = "num",
  display,
  disabled,
  right,
}: {
  label: ReactNode
  value: number
  onChange: (v: number) => void
  min: number
  max: number
  step?: number
  kind?: NumKind
  display?: string
  disabled?: boolean
  right?: ReactNode
}) {
  const clamped = Math.min(max, Math.max(min, value))
  return (
    <div className={cn("py-1", disabled && "opacity-50")}>
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-xs text-text-secondary">{label}</span>
        <div className="flex items-center gap-2">
          {right}
          {display !== undefined ? (
            <span className="font-mono text-xs text-text tabular-nums">{display}</span>
          ) : (
            <NumInput value={value} onChange={onChange} kind={kind} disabled={disabled} className="w-[92px]" />
          )}
        </div>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={clamped}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1.5 w-full cursor-pointer accent-[rgb(var(--color-accent))]"
        aria-label={typeof label === "string" ? label : undefined}
      />
    </div>
  )
}

/** Small checkbox with label. */
export function Check({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
}) {
  return (
    <label className="flex cursor-pointer items-center gap-1 text-[11px] text-text-secondary">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-3 w-3 accent-[rgb(var(--color-accent))]"
      />
      {label}
    </label>
  )
}

/** Section header inside the drivers panel. */
export function Section({ title, children, meta }: { title: string; children: ReactNode; meta?: ReactNode }) {
  return (
    <div className="border-t border-border pt-3 first:border-t-0 first:pt-0">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-[11px] font-medium tracking-wider text-text-label">{title}</span>
        {meta && <span className="font-mono text-[11px] text-text-label">{meta}</span>}
      </div>
      {children}
    </div>
  )
}
