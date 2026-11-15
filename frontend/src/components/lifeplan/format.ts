/** German number formatting for the Lebensplan page (de-DE, "1.234.567 €"). */

const LOCALE = "de-DE"

/** Full amount: `1.234.567 €` (minus sign `−`). */
export function eur(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—"
  const sign = v < 0 ? "−" : ""
  return `${sign}${Math.round(Math.abs(v)).toLocaleString(LOCALE)} €`
}

/** Compact amount: `2,1 Mio €`, `850 Tsd €`, `900 €`. */
export function eurShort(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—"
  const sign = v < 0 ? "−" : ""
  const a = Math.abs(v)
  if (a >= 1_000_000)
    return `${sign}${(a / 1_000_000).toLocaleString(LOCALE, { maximumFractionDigits: a >= 10_000_000 ? 1 : 2 })} Mio €`
  if (a >= 10_000) return `${sign}${Math.round(a / 1000).toLocaleString(LOCALE)} Tsd €`
  return `${sign}${Math.round(a).toLocaleString(LOCALE)} €`
}

/** Axis tick: `2,1 Mio`, `850 Tsd`. */
export function axisShort(v: number): string {
  return eurShort(v).replace(" €", "")
}

/** Percent from a fraction: 0.042 → `4,2 %`. */
export function pct(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "—"
  return `${(v * 100).toLocaleString(LOCALE, { maximumFractionDigits: digits })} %`
}
