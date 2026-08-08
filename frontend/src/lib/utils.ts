import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

/** Merge Tailwind class lists, resolving conflicts (last wins). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/** Locale for all money/number display — German grouping (thousands dot,
 *  decimal comma), per the Cash Flow number-format convention. */
const NUMBER_LOCALE = "de-DE"

/**
 * Format a number as currency, German-locale Cockpit style: `€1.838,09`
 * (symbol directly against the number, dot-grouped thousands, comma decimal,
 * real minus sign before the symbol for negatives — `−€1.498,00`).
 */
export function formatCurrency(
  value: number | null | undefined,
  currency: string = "EUR",
  decimals: number = 2,
): string {
  if (value == null || Number.isNaN(value)) return "—"
  const symbols: Record<string, string> = { EUR: "€", USD: "$", GBP: "£" }
  const symbol = symbols[currency] ?? currency
  const sign = value < 0 ? "−" : ""
  const formatted = Math.abs(value).toLocaleString(NUMBER_LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
  return `${sign}${symbol}${formatted}`
}

/**
 * Format a signed percentage in the Cockpit style: `+2,4 %` / `−1,1 %`.
 * Returns an em-dash for missing values.
 */
export function formatPercent(
  value: number | null | undefined,
  decimals: number = 1,
): string {
  if (value == null || Number.isNaN(value)) return "—"
  const sign = value > 0 ? "+" : value < 0 ? "−" : ""
  const formatted = Math.abs(value).toLocaleString(NUMBER_LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
  return `${sign}${formatted} %`
}

/** Format a plain number with grouped thousands, German locale. */
export function formatNumber(
  value: number | null | undefined,
  decimals: number = 0,
): string {
  if (value == null || Number.isNaN(value)) return "—"
  return value.toLocaleString(NUMBER_LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

/** Current local date as an ISO `YYYY-MM-DD` string. */
export function isoDate(d: Date = new Date()): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}
