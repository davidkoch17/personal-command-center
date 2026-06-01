import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type {
  ProjectCard,
  ProjectCreateRequest,
  ProjectWorkspace,
} from "@/lib/types"

export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: () => api.get<ProjectCard[]>("/api/projects"),
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
