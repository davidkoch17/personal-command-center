import { useCallback, useEffect, useState } from "react"
import type { ConstraintSet } from "@/hooks/useOptimizationConstrained"

const STORAGE_KEY = "pcc.constraint_scenarios"
const EVENT = "pcc:constraint_scenarios"

export interface ConstraintScenario {
  name: string
  savedAt: string
  constraints: ConstraintSet
}

function read(): ConstraintScenario[] {
  if (typeof window === "undefined") return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function write(scenarios: ConstraintScenario[]) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(scenarios))
  window.dispatchEvent(new Event(EVENT))
}

/**
 * Saved constraint-modal scenarios (D8's "Save as scenario") — localStorage +
 * custom DOM event, the same pattern useBenchmark/useReportingCurrency use.
 * Local-only by design: these are exploratory presets for the modal, not
 * portfolio state, so no backend persistence.
 */
export function useConstraintScenarios() {
  const [scenarios, setScenarios] = useState<ConstraintScenario[]>(read)

  useEffect(() => {
    const sync = () => setScenarios(read())
    window.addEventListener(EVENT, sync)
    window.addEventListener("storage", sync)
    return () => {
      window.removeEventListener(EVENT, sync)
      window.removeEventListener("storage", sync)
    }
  }, [])

  const saveScenario = useCallback((name: string, constraints: ConstraintSet) => {
    const trimmed = name.trim()
    if (!trimmed) return
    const next = [
      ...read().filter((s) => s.name !== trimmed),
      { name: trimmed, savedAt: new Date().toISOString(), constraints },
    ]
    write(next)
    setScenarios(next)
  }, [])

  const deleteScenario = useCallback((name: string) => {
    const next = read().filter((s) => s.name !== name)
    write(next)
    setScenarios(next)
  }, [])

  return { scenarios, saveScenario, deleteScenario }
}
