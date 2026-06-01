import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { RunStatus } from "@/lib/types"

/** Statuses that mean the run is still in flight (drives auto-refresh). */
const ACTIVE = new Set(["running", "pending", "in_progress", "started", "launched"])

export function isRunActive(status: string | undefined): boolean {
  return ACTIVE.has((status ?? "").toLowerCase())
}

export function useRuns() {
  return useQuery({
    queryKey: ["runs"],
    queryFn: () => api.get<{ runs: RunStatus[] }>("/api/runs"),
    // Auto-refresh every 5s only while at least one run is active.
    refetchInterval: (query) => {
      const runs = query.state.data?.runs ?? []
      return runs.some((r) => isRunActive(r.status)) ? 5000 : false
    },
  })
}

export function useRunStatus(runId: string | undefined) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.get<RunStatus>(`/api/runs/${runId}`),
    enabled: !!runId,
  })
}
