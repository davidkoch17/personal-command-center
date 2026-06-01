import { useMutation } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { TaxScenarioRequest } from "@/lib/types"

interface RunResponse {
  ok: boolean
  run_id: string
  skill?: string
}

/**
 * Launch a registered background skill (`POST /api/skills/{name}/run`).
 * Returns a run_id immediately; track it on the Background Runs page.
 */
export function useRunSkill() {
  return useMutation({
    mutationFn: ({
      skill,
      args,
      label,
    }: {
      skill: string
      args?: Record<string, unknown>
      label?: string
    }) =>
      api.post<RunResponse>(`/api/skills/${skill}/run`, {
        args: args ?? {},
        label,
      }),
  })
}

/** Tax scenario has its own endpoint (writes a dated MD file). */
export function useTaxScenario() {
  return useMutation({
    mutationFn: (req: TaxScenarioRequest) =>
      api.post<RunResponse>("/api/money/tax-scenario", req),
  })
}
