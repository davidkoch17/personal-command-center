import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { InboxActionRequest, InboxCaptureRequest } from "@/lib/types"

export interface InboxItem {
  filename: string
  mtime: string
  preview: string
}

export function useInbox() {
  return useQuery({
    queryKey: ["inbox"],
    queryFn: () => api.get<InboxItem[]>("/api/inbox"),
  })
}

export function useInboxCapture() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: InboxCaptureRequest) =>
      api.post<{ ok: boolean; filename: string; path: string }>(
        "/api/inbox/capture",
        req,
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inbox"] }),
  })
}

export function useInboxAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      filename,
      req,
    }: {
      filename: string
      req: InboxActionRequest
    }) =>
      api.post<{ ok: boolean; action: string }>(
        `/api/inbox/${encodeURIComponent(filename)}/action`,
        req,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inbox"] })
      // convert_to_task mutates the task file too.
      qc.invalidateQueries({ queryKey: ["tasks"] })
    },
  })
}
