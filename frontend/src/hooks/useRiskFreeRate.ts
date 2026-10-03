import { useCallback, useEffect, useState } from "react"

/** Mirrors core.config.DEFAULT_RISK_FREE_RATE — what the backend uses when no ``rfr`` is sent. */
export const DEFAULT_RFR = 0.04
export const MAX_RFR = 0.25

const STORAGE_KEY = "pcc.rfr"
const EVENT = "pcc:rfr"

function clamp(v: number): number {
  return Math.min(MAX_RFR, Math.max(0, v))
}

function read(): number {
  if (typeof window === "undefined") return DEFAULT_RFR
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    const v = raw == null ? NaN : Number(raw)
    return Number.isFinite(v) ? clamp(v) : DEFAULT_RFR
  } catch {
    return DEFAULT_RFR
  }
}

/**
 * Shared risk-free rate (fraction, 0.04 = 4%) — the setting behind every Sharpe, Sortino and
 * CAPM figure in the app. Persisted in localStorage and synced across components via a custom
 * DOM event, same pattern as useBenchmark (pcc.benchmark / pcc:benchmark).
 *
 * Every hook that fetches a rate-dependent number reads this and puts it in its React Query
 * key, so changing the rate refetches exactly those queries — no manual invalidation needed.
 */
export function useRiskFreeRate(): [number, (rate: number) => void] {
  const [rfr, setState] = useState<number>(read)

  useEffect(() => {
    const sync = () => setState(read())
    window.addEventListener(EVENT, sync)
    window.addEventListener("storage", sync)
    return () => {
      window.removeEventListener(EVENT, sync)
      window.removeEventListener("storage", sync)
    }
  }, [])

  const setRfr = useCallback((rate: number) => {
    const next = clamp(rate)
    try {
      window.localStorage.setItem(STORAGE_KEY, String(next))
    } catch {
      /* private mode etc. — keep the in-memory value */
    }
    setState(next)
    window.dispatchEvent(new Event(EVENT))
  }, [])

  return [rfr, setRfr]
}
