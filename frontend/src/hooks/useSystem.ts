import { useMutation, useQuery } from "@tanstack/react-query"
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
  finance_source_mtime?: string | number | null
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

export function useClearCache() {
  return useMutation({
    mutationFn: () => api.post<{ ok: boolean; detail?: string }>("/api/system/clear-cache"),
  })
}

/** v3 configuration surfaced on the Settings page (GET /api/system/config). */
export interface SystemConfig {
  capture_paths: {
    news_captures: string
    voice_notes: string
    finance_imports: string
    watcher_interval_seconds: number
  }
  snapshot: { time: string; scheduler: string }
  watchlist: { file: string; tiers: string[] }
  tailscale: { configured: boolean; note: string }
  known_projects: string[]
  evercore_start: string
}

export function useSystemConfig() {
  return useQuery({
    queryKey: ["system", "config"],
    queryFn: () => api.get<SystemConfig>("/api/system/config"),
    staleTime: 5 * 60_000,
  })
}

/** A recorded "we are here" marker (modules/system/checkpoints.py). */
export interface Checkpoint {
  timestamp: string
  label: string
  notes: string
  snapshot: Record<string, unknown>
}

export function useCheckpoints() {
  return useQuery({
    queryKey: ["system", "checkpoints"],
    queryFn: () => api.get<{ checkpoints: Checkpoint[]; latest: Checkpoint | null }>("/api/system/checkpoints"),
    staleTime: 30_000,
  })
}
