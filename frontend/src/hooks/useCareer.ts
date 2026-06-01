import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { CareerChecklistToggleRequest, CareerSkillRequest } from "@/lib/types"

export interface ChecklistEntry {
  text: string
  checked: boolean
  [k: string]: unknown
}

export interface CareerOverview {
  start_date: string
  days_until_start: number | null
  onboarding_done: number
  onboarding_total: number
  technicals_done: number
  technicals_total: number
}

export interface CareerWorkspaceState extends CareerOverview {
  onboarding: ChecklistEntry[]
  technicals: ChecklistEntry[]
}

export function useCareerOverview() {
  return useQuery({
    queryKey: ["career", "overview"],
    queryFn: () => api.get<CareerOverview>("/api/career"),
  })
}

export function useCareerWorkspace() {
  return useQuery({
    queryKey: ["career", "workspace"],
    queryFn: () => api.get<CareerWorkspaceState>("/api/career/workspace"),
  })
}

export function useToggleChecklist() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: CareerChecklistToggleRequest) =>
      api.post<{ ok: boolean; checked: boolean }>("/api/career/checklist/toggle", req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["career"] })
    },
  })
}

export function useRunCareerSkill() {
  return useMutation({
    mutationFn: (req: CareerSkillRequest) =>
      api.post<{ ok: boolean; run_id: string }>("/api/career/skill", req),
  })
}
