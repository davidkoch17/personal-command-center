import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { api } from "@/lib/api"
import type {
  MoneySnapshot,
  WatchlistAddRequest,
  WatchlistHypothesisRequest,
} from "@/lib/types"

/** A holdings record — raw DataFrame columns (keys include € and spaces). */
export type HoldingRow = Record<string, string | number | null>

export interface PortfolioSnapshotResponse {
  total_value: number
  position_count: number
  last_snapshot_date: string | null
  market_value_total: number
  cash_deployable: number
  holdings: HoldingRow[]
}

export interface WatchlistResponse {
  tiers: Record<string, WatchlistEntry[]>
  count: number
  valid_statuses: string[]
}

export interface WatchlistEntry {
  ticker: string
  name: string
  status: string
  tier: string
  added?: string | null
  notes?: string
  price?: {
    last_close: number | null
    week_change_pct: number | null
    month_change_pct: number | null
    currency: string | null
  } | null
}

export interface PerformanceResponse {
  period: string
  by_month: Record<string, string | number | null>[]
  change_pct: number | null
}

export interface AllocationsResponse {
  total_value: number
  by_type: { type: string; value: number; weight_pct: number | null }[]
  by_position: {
    name: string
    type: string
    value: number
    weight_pct: number | null
  }[]
}

export interface CashflowResponse {
  months: number
  cashflow: { month: string; income: number; expenses: number }[]
}

export interface CategoriesResponse {
  months: number
  categories: Record<string, string | number | null>[]
}

export function usePortfolioSnapshot() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: () => api.get<PortfolioSnapshotResponse>("/api/portfolio"),
  })
}

export function usePortfolioPerformance(period = "ytd") {
  return useQuery({
    queryKey: ["portfolio", "performance", period],
    queryFn: () =>
      api.get<PerformanceResponse>(`/api/portfolio/performance?period=${period}`),
  })
}

export function usePortfolioAllocations() {
  return useQuery({
    queryKey: ["portfolio", "allocations"],
    queryFn: () => api.get<AllocationsResponse>("/api/portfolio/allocations"),
  })
}

export function useMoneyCashflow(months = 12) {
  return useQuery({
    queryKey: ["money", "cashflow", months],
    queryFn: () => api.get<CashflowResponse>(`/api/money/cashflow?months=${months}`),
  })
}

export function useMoneyCategories(months = 6) {
  return useQuery({
    queryKey: ["money", "categories", months],
    queryFn: () =>
      api.get<CategoriesResponse>(`/api/money/categories?months=${months}`),
  })
}

export function useMoneySnapshot() {
  return useQuery({
    queryKey: ["money", "snapshot"],
    queryFn: () => api.get<MoneySnapshot>("/api/money/snapshot"),
  })
}

export function useWatchlist(prices = false) {
  return useQuery({
    queryKey: ["watchlist", { prices }],
    queryFn: () => api.get<WatchlistResponse>(`/api/watchlist?prices=${prices}`),
  })
}

export interface WatchlistDossier {
  ticker: string
  name: string
  status: string | null
  tier: string | null
  price: Record<string, unknown> | null
  news: Record<string, unknown>[]
  filings: Record<string, unknown>[]
  hypotheses: Record<string, unknown>[]
  signals: Record<string, unknown>[]
  position_note: string | null
}

export function useWatchlistDossier(ticker: string | undefined) {
  return useQuery({
    queryKey: ["watchlist", "dossier", ticker],
    queryFn: () =>
      api.get<WatchlistDossier>(`/api/watchlist/${encodeURIComponent(ticker!)}`),
    enabled: !!ticker,
  })
}

/**
 * Fetch dossiers for many tickers at once (shared per-ticker cache with
 * `useWatchlistDossier`). Each dossier carries news + filings + hypotheses +
 * signals, so the aggregate tabs derive from one fetch per name. Lazy: pass
 * `enabled = false` until an aggregate tab is opened (each call hits live data
 * sources).
 */
export function useWatchlistDossiers(tickers: string[], enabled: boolean) {
  return useQueries({
    queries: tickers.map((t) => ({
      queryKey: ["watchlist", "dossier", t],
      queryFn: () =>
        api.get<WatchlistDossier>(`/api/watchlist/${encodeURIComponent(t)}`),
      enabled: enabled && !!t,
      staleTime: 60_000,
    })),
  })
}

export function useAddWatchlist() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: WatchlistAddRequest) =>
      api.post<{ ok: boolean; ticker: string }>("/api/watchlist", req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlist"] }),
  })
}

export function useAddHypothesis(ticker: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: WatchlistHypothesisRequest) =>
      api.post<{ ok: boolean; message: string }>(
        `/api/watchlist/${encodeURIComponent(ticker!)}/hypothesis`,
        req,
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["watchlist", "dossier", ticker] }),
  })
}
