import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

/** One row of the Skills & Agents Registry (GET /api/skills/registry). */
export interface RegistryEntry {
  key: string
  label: string
  kind: "skill" | "agent"
  domain: string
  description: string
  health: "ok" | "due" | "failed" | "never"
  last_run_at?: string | null
  last_run_id?: string | null
  last_run_status?: string | null
  run_skill?: string | null
  prompt_arg?: string | null
  run_target?: string | null
  cadence_days?: number | null
  note?: string | null
  disabled: boolean
  disabled_at?: string | null
  disabled_reason?: string | null
}

export function useRegistry() {
  return useQuery({
    queryKey: ["skills", "registry"],
    queryFn: () => api.get<{ entries: RegistryEntry[] }>("/api/skills/registry"),
    staleTime: 30_000,
  })
}

/** Soft-disable (archive) a registry entry — reversible. */
export function useDisableEntry() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key, reason }: { key: string; reason?: string }) =>
      api.post(`/api/skills/registry/${key}/disable`, { reason }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["skills", "registry"] }),
  })
}

/** Restore a previously disabled registry entry. */
export function useEnableEntry() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (key: string) => api.post(`/api/skills/registry/${key}/enable`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["skills", "registry"] }),
  })
}
