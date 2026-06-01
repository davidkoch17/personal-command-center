import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { Task, TaskAddRequest, TaskToggleRequest } from "@/lib/types"

/** Section order as returned by the backend (`/api/tasks`). */
export const TASK_SECTIONS = [
  "Today",
  "This weekend",
  "This week",
  "This month",
  "Waiting for",
] as const

export type TasksBySection = Record<string, Task[]>

export function useTasks() {
  return useQuery({
    queryKey: ["tasks"],
    queryFn: () => api.get<TasksBySection>("/api/tasks"),
  })
}

export function useToggleTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: TaskToggleRequest) =>
      api.post<{ ok: boolean; new_state: boolean }>("/api/tasks/toggle", req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  })
}

export function useAddTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: TaskAddRequest) =>
      api.post<{ ok: boolean }>("/api/tasks/add", req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  })
}
