import { QueryClient } from "@tanstack/react-query"

/**
 * Shared TanStack Query client. Server data (vault, market prices) is read-mostly
 * and a touch stale-tolerant, so we keep a 30s staleTime and skip refetch on focus
 * to avoid hammering the FastAPI backend / yfinance.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})
