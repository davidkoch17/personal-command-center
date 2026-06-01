import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { SearchResponse } from "@/lib/types"

/**
 * Vault full-text search. Pass an already-debounced query. Disabled until the
 * query has more than one character (matches the Home search-bar threshold).
 */
export function useSearchVault(query: string) {
  const trimmed = query.trim()
  return useQuery({
    queryKey: ["search", trimmed],
    queryFn: () =>
      api.get<SearchResponse>(`/api/search?q=${encodeURIComponent(trimmed)}`),
    enabled: trimmed.length > 1,
    staleTime: 10_000,
  })
}
