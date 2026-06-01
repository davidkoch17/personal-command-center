import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

/**
 * System status (vault stats + integration health). May expose an
 * `info_barrier` flag once the backend surfaces `info_barrier_active()`; we read
 * it defensively so the info-barrier banner lights up automatically when present.
 */
export interface SystemStatus {
  vault_path?: string
  vault_exists?: boolean
  info_barrier?: boolean
  counts?: Record<string, number>
  integrations?: Record<string, unknown>
  [k: string]: unknown
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ["system", "status"],
    queryFn: () => api.get<SystemStatus>("/api/system/status"),
    staleTime: 60_000,
  })
}

/** True only when the backend explicitly reports the info barrier active. */
export function useInfoBarrierActive(): boolean {
  const { data } = useSystemStatus()
  return data?.info_barrier === true
}
