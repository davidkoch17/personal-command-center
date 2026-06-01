import { QueryCache, QueryClient } from "@tanstack/react-query"
import { ApiError } from "@/lib/api"
import { toast } from "@/lib/toast-store"

function describe(error: unknown): string {
  if (error instanceof ApiError) return `${error.status}: ${error.message}`.slice(0, 160)
  return String((error as Error)?.message ?? error).slice(0, 160)
}

/**
 * Shared TanStack Query client. Server data (vault, market prices) is read-mostly
 * and a touch stale-tolerant, so we keep a 30s staleTime and skip refetch on focus
 * to avoid hammering the FastAPI backend / yfinance. A global cache error handler
 * surfaces failures as a toast so a flaky endpoint never crashes the page.
 */
export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      // Only surface the first failure (avoid toast spam on retries).
      if (query.state.fetchFailureCount <= 1) {
        toast.error("request failed", describe(error))
      }
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})
