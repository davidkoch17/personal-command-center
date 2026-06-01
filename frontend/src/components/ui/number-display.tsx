import { cn, formatCurrency, formatNumber, formatPercent } from "@/lib/utils"
import { useTween } from "@/hooks/useTween"

interface NumberDisplayProps {
  value: number | null | undefined
  /** How to format the raw value. */
  format?: "plain" | "currency" | "percent"
  currency?: string
  decimals?: number
  /** Emphasize in accent navy (metrics, P&L headline figures). */
  emphasized?: boolean
  /**
   * Color the value by sign (success when positive, danger when negative).
   * Useful for P&L / deltas. Takes precedence over `emphasized`.
   */
  signed?: boolean
  /** Tween from the previous value to the new one (300ms ease-out). */
  animate?: boolean
  className?: string
}

/**
 * Monospace numeric value, weight 500, in the Cockpit number style. Numbers are
 * always monospace; accent color marks emphasis, semantic color marks sign.
 */
export function NumberDisplay({
  value,
  format = "plain",
  currency = "EUR",
  decimals,
  emphasized = false,
  signed = false,
  animate = false,
  className,
}: NumberDisplayProps) {
  const tweened = useTween(animate ? value : undefined)
  const shown = animate && tweened != null ? tweened : value

  let text: string
  switch (format) {
    case "currency":
      text = formatCurrency(shown, currency)
      break
    case "percent":
      text = formatPercent(shown, decimals ?? 1)
      break
    default:
      text = formatNumber(shown, decimals ?? 0)
  }

  const hasValue = value != null && !Number.isNaN(value)
  const signColor =
    signed && hasValue
      ? value > 0
        ? "text-success"
        : value < 0
          ? "text-danger"
          : "text-text"
      : undefined

  return (
    <span
      className={cn(
        "font-mono font-medium tabular-nums",
        signColor ?? (emphasized ? "text-accent" : "text-text"),
        className,
      )}
    >
      {text}
    </span>
  )
}
