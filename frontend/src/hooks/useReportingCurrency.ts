import { useCallback, useEffect, useState } from "react"

export type ReportingCurrency = "EUR" | "USD"

const STORAGE_KEY = "pcc.reportingCurrency"
const DEFAULT: ReportingCurrency = "EUR"
const EVENT = "pcc:reporting-currency"

function read(): ReportingCurrency {
  if (typeof window === "undefined") return DEFAULT
  const v = window.localStorage.getItem(STORAGE_KEY)
  return v === "USD" || v === "EUR" ? v : DEFAULT
}

/**
 * Reporting-currency preference (EUR default) persisted in localStorage and
 * synced across the tab via a custom event, so the Portfolio currency toggle
 * re-renders every panel that reads it. Phase 15e, Section 1.3.
 */
export function useReportingCurrency(): [ReportingCurrency, (c: ReportingCurrency) => void] {
  const [currency, setCurrencyState] = useState<ReportingCurrency>(read)

  useEffect(() => {
    const sync = () => setCurrencyState(read())
    window.addEventListener(EVENT, sync)
    window.addEventListener("storage", sync)
    return () => {
      window.removeEventListener(EVENT, sync)
      window.removeEventListener("storage", sync)
    }
  }, [])

  const setCurrency = useCallback((c: ReportingCurrency) => {
    window.localStorage.setItem(STORAGE_KEY, c)
    setCurrencyState(c)
    window.dispatchEvent(new Event(EVENT))
  }, [])

  return [currency, setCurrency]
}
