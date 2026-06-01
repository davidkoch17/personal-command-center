import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type {
  IdeaCard,
  IdeaCreateRequest,
  IdeaDecisionRequest,
} from "@/lib/types"

export interface IdeaStage {
  stage_key: string
  slug: string
  title: string
  filename: string
  status: "pending" | "done" | "stale"
  exists: boolean
  mtime: string | null
  content: string
}

export interface IdeaWorkspaceState {
  name: string
  stages_complete: number
  total_stages: number
  stages: IdeaStage[]
  brief: string
  overrides: string
  master: string
}

export function useIdeas() {
  return useQuery({
    queryKey: ["ideas"],
    queryFn: () => api.get<IdeaCard[]>("/api/ideas"),
  })
}

export function useIdeaWorkspace(name: string | undefined) {
  return useQuery({
    queryKey: ["idea", name],
    queryFn: () =>
      api.get<IdeaWorkspaceState>(`/api/ideas/${encodeURIComponent(name!)}`),
    enabled: !!name,
  })
}

export function useCreateIdea() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: IdeaCreateRequest) =>
      api.post<{ ok: boolean; name: string; path: string }>("/api/ideas", req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ideas"] }),
  })
}

export function useRunStage(name: string | undefined) {
  return useMutation({
    mutationFn: (stageKey: string) =>
      api.post<{ ok: boolean; run_id: string }>(
        `/api/ideas/${encodeURIComponent(name!)}/run-stage`,
        { stage_key: stageKey },
      ),
  })
}

export function useRunAllStages(name: string | undefined) {
  return useMutation({
    mutationFn: () =>
      api.post<{ ok: boolean; run_id: string }>(
        `/api/ideas/${encodeURIComponent(name!)}/run-all`,
        {},
      ),
  })
}

export function useDecideIdea(name: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: IdeaDecisionRequest) =>
      api.post<{ ok: boolean }>(
        `/api/ideas/${encodeURIComponent(name!)}/decide`,
        req,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["idea", name] })
      qc.invalidateQueries({ queryKey: ["ideas"] })
    },
  })
}

export function useUpdateOverrides(name: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (text: string) =>
      api.post<{ ok: boolean }>(
        `/api/ideas/${encodeURIComponent(name!)}/overrides`,
        { text },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["idea", name] }),
  })
}
