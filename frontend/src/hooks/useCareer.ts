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

export interface CareerActivityItem {
  name: string
  rel_path: string
  folder: string
  modified: string
}

export function useCareerActivity(limit = 8) {
  return useQuery({
    queryKey: ["career", "activity", limit],
    queryFn: () =>
      api.get<{ items: CareerActivityItem[] }>(`/api/career/activity?limit=${limit}`),
  })
}

export interface CareerModelStatus {
  status: "ready" | "not_started"
  found: boolean
  path: string | null
  name: string | null
  last_modified: string | null
  expected_path: string
  note: string
}

export function useCareerModel() {
  return useQuery({
    queryKey: ["career", "model"],
    queryFn: () => api.get<CareerModelStatus>("/api/career/model"),
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
