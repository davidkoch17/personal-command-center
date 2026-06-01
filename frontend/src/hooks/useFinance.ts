import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { MoneySnapshot } from "@/lib/types"

export interface PortfolioSnapshotResponse {
  total_value: number
  position_count: number
  last_snapshot_date: string | null
  market_value_total: number
  cash_deployable: number
  holdings: Record<string, unknown>[]
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

export function usePortfolioSnapshot() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: () => api.get<PortfolioSnapshotResponse>("/api/portfolio"),
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
