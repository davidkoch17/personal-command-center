import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type {
  BriefingCard,
  ProjectCard,
  ProjectCreateRequest,
  ProjectWorkspace,
  VentureAgents,
  VentureRun,
} from "@/lib/types"
import { isRunActive } from "@/hooks/useRuns"

export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: () => api.get<ProjectCard[]>("/api/projects"),
  })
}

/** Latest weekly briefing for the Projects-pillar card (99_System/Briefings/). */
export function useLatestBriefing() {
  return useQuery({
    queryKey: ["briefing", "latest"],
    queryFn: () => api.get<BriefingCard>("/api/projects/briefing"),
  })
}

export function useProjectWorkspace(id: string | undefined) {
  return useQuery({
    queryKey: ["project", id],
    queryFn: () => api.get<ProjectWorkspace>(`/api/projects/${id}`),
    enabled: !!id,
  })
}

export function useToggleNextStep(id: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (lineIndex: number) =>
      api.post<{ ok: boolean; new_state: boolean }>(
        `/api/projects/${id}/next-step/toggle`,
        { line_index: lineIndex },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["project", id] })
      qc.invalidateQueries({ queryKey: ["projects"] })
    },
  })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: ProjectCreateRequest) =>
      api.post<{ ok: boolean; path: string; folder: string }>(
        "/api/projects",
        req,
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  })
}

// --- Venture agents (Page 4, Layer B — the "department") --------------------

/** The venture's agent roster + per-agent last-run health (from _agents.json). */
export function useVentureAgents(id: string | undefined) {
  return useQuery({
    queryKey: ["venture-agents", id],
    queryFn: () => api.get<VentureAgents>(`/api/projects/${id}/agents`),
    enabled: !!id,
  })
}

/** Launch a manifest agent in the background; returns a run_id. */
export function useRunVentureAgent(id: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (agentKey: string) =>
      api.post<{ ok: boolean; run_id: string; agent_key: string }>(
        `/api/projects/${id}/agents/${agentKey}/run`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["venture-runs", id] })
      qc.invalidateQueries({ queryKey: ["venture-agents", id] })
    },
  })
}

/** This venture's agent run history (newest first); polls while a run is live. */
export function useVentureRuns(id: string | undefined) {
  return useQuery({
    queryKey: ["venture-runs", id],
    queryFn: () => api.get<{ runs: VentureRun[] }>(`/api/projects/${id}/runs`),
    enabled: !!id,
    refetchInterval: (query) =>
      query.state.data?.runs?.some((r) => isRunActive(r.status ?? undefined))
        ? 5000
        : false,
  })
}

/** Append a timestamped entry to the venture's Project_Log.md (WIRE D3). */
export function useAppendProjectLog(id: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (note: string) =>
      api.post<{ ok: boolean; path: string }>(`/api/projects/${id}/log`, { note }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project", id] }),
  })
}
