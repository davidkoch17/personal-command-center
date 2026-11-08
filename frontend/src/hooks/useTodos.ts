import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, ApiError } from "@/lib/api"
import { toast } from "@/lib/toast-store"

// --- Types (mirror backend/api/todos.py + the todos.json schema) -------------

export type TodoStatus = "open" | "in_progress" | "waiting" | "done"

export interface TodoSubtask {
  title: string
  done: boolean
  priority?: number
}

export interface Todo {
  id: string
  title: string
  area: string
  priority: number
  status: TodoStatus
  due: string | null
  notes: string
  subtasks: TodoSubtask[]
}

export interface TodosResponse {
  version: number
  updated: string
  tasks: Todo[]
  path: string
  statuses: TodoStatus[]
}

export type TodoFields = Partial<Omit<Todo, "id">>

const KEY = ["todos"]

/** The whole todos.json. Refetches on focus so chat-Claude edits show up. */
export function useTodos() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => api.get<TodosResponse>("/api/todos"),
    refetchOnWindowFocus: true,
    refetchInterval: 60_000,
  })
}

function errorDetail(err: unknown): string | undefined {
  if (err instanceof ApiError) {
    try {
      return JSON.parse(err.message).detail ?? err.message
    } catch {
      return err.message
    }
  }
  return err instanceof Error ? err.message : undefined
}

function useTodoMutation<V>(fn: (vars: V) => Promise<unknown>, failMsg: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
    onError: (err) => toast.error(failMsg, errorDetail(err)),
  })
}

export function useCreateTodo() {
  return useTodoMutation((fields: TodoFields) => api.post<Todo>("/api/todos", fields), "could not create task")
}

export function useUpdateTodo() {
  return useTodoMutation(
    ({ id, fields }: { id: string; fields: TodoFields }) =>
      api.patch<Todo>(`/api/todos/${encodeURIComponent(id)}`, fields),
    "could not save task",
  )
}

export function useToggleSubtask() {
  return useTodoMutation(
    ({ id, index, done }: { id: string; index: number; done: boolean }) =>
      api.put<Todo>(`/api/todos/${encodeURIComponent(id)}/subtasks/${index}`, { done }),
    "could not update subtask",
  )
}

export function useDeleteTodo() {
  return useTodoMutation(
    (id: string) => api.delete(`/api/todos/${encodeURIComponent(id)}`),
    "could not delete task",
  )
}
