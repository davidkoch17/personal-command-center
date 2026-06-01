import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

export interface DiagnosticCheck {
  name: string
  status: string // "ok" | "not_configured" | "error"
  detail?: string
}

/**
 * Integration health check. The backend exposes this as GET (the spec assumed
 * POST); the Settings "run health check" button just refetches. Lazy: enabled
 * is false until first triggered, so it doesn't hit live integrations on load.
 */
export function useDiagnostics(enabled: boolean) {
  return useQuery({
    queryKey: ["diagnostics"],
    queryFn: () => api.get<{ checks: DiagnosticCheck[] }>("/api/integrations/diagnostics"),
    enabled,
    staleTime: 0,
  })
}
