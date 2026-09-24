import { useCallback, useEffect, useState } from "react"

/** Benchmark keys — matches core.config.BENCHMARKS / DEFAULT_BENCHMARK. */
export type BenchmarkKey = "MSCI_WORLD" | "SPY" | "DAX" | "STOXX_600"

const STORAGE_KEY = "pcc.benchmark"
const DEFAULT: BenchmarkKey = "MSCI_WORLD"
const EVENT = "pcc:benchmark"
const VALID: BenchmarkKey[] = ["MSCI_WORLD", "SPY", "DAX", "STOXX_600"]

function read(): BenchmarkKey {
  if (typeof window === "undefined") return DEFAULT
  const v = window.localStorage.getItem(STORAGE_KEY)
  return (VALID as string[]).includes(v ?? "") ? (v as BenchmarkKey) : DEFAULT
}

/**
 * Shared "Comparison benchmark" selection (MSCI World default), persisted in
 * localStorage and synced across the tab via a custom event — same pattern as
 * useReportingCurrency. The Risk tab's dropdown writes here so every other
 * consumer (e.g. per-holding beta on the Holdings tab) recomputes against the
 * same benchmark instead of each keeping an independent, silently-diverging
 * local selection.
 */
export function useBenchmark(): [BenchmarkKey, (b: BenchmarkKey) => void] {
  const [benchmark, setBenchmarkState] = useState<BenchmarkKey>(read)

  useEffect(() => {
    const sync = () => setBenchmarkState(read())
    window.addEventListener(EVENT, sync)
    window.addEventListener("storage", sync)
    return () => {
      window.removeEventListener(EVENT, sync)
      window.removeEventListener("storage", sync)
    }
  }, [])

  const setBenchmark = useCallback((b: BenchmarkKey) => {
    window.localStorage.setItem(STORAGE_KEY, b)
    setBenchmarkState(b)
    window.dispatchEvent(new Event(EVENT))
  }, [])

  return [benchmark, setBenchmark]
}
