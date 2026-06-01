import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

/** Merge Tailwind class lists, resolving conflicts (last wins). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/**
 * Format a number as currency in the Cockpit style: `€ 4,807.30`
 * (symbol, space, grouped thousands, two decimals).
 */
export function formatCurrency(
  value: number | null | undefined,
  currency: string = "EUR",
): string {
  if (value == null || Number.isNaN(value)) return "—"
  const symbols: Record<string, string> = { EUR: "€", USD: "$", GBP: "£" }
  const symbol = symbols[currency] ?? currency
  const formatted = value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  return `${symbol} ${formatted}`
}

/**
 * Format a signed percentage in the Cockpit style: `+2.4 %` / `-1.1 %`.
 * Returns an em-dash for missing values.
 */
export function formatPercent(
  value: number | null | undefined,
  decimals: number = 1,
): string {
  if (value == null || Number.isNaN(value)) return "—"
  const sign = value > 0 ? "+" : ""
  return `${sign}${value.toFixed(decimals)} %`
}

/** Format a plain number with grouped thousands. */
export function formatNumber(
  value: number | null | undefined,
  decimals: number = 0,
): string {
  if (value == null || Number.isNaN(value)) return "—"
  return value.toLocaleString("en-US", {
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
