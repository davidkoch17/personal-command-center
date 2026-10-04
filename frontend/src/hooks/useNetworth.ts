import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

export type NetworthPeriod = "1M" | "3M" | "YTD" | "1Y" | "ALL"

export interface NetworthBreakdown {
  bank_cash: number
  brokerage_cash: number
  etfs: number
  single_stocks: number
  crypto: number
  wild_cards: number
  liabilities: number
  total: number
}

export interface NetworthTrendPoint {
  date: string
  net_worth_eur: number
}

export interface NetworthTrend {
  period: NetworthPeriod
  series: NetworthTrendPoint[]
  available: boolean
}

export type MilestoneStatus = "on_track" | "paused" | "reached" | "insufficient_history"

export interface NetworthMilestone {
  available: boolean
  reason?: string
  label?: string
  current?: number
  target?: number
  pct?: number | null
  monthly_rate?: number | null
  months_to_goal?: number | null
  projected_date?: string | null
  status?: MilestoneStatus
}

export interface NetworthCashAccount {
  name: string
  value: number
}

export interface NetworthHolding {
  ticker: string
  name: string
  value: number
  pct_1m: number | null
  pct_1y: number | null
  gain: number | null
}

export interface NetworthAccounts {
  cash: { total: number; accounts: NetworthCashAccount[] }
  portfolio: { total: number; holdings: NetworthHolding[] }
}

export interface NetworthSnapshotResponse {
  breakdown: NetworthBreakdown
  delta_this_month: number | null
  trend: NetworthTrend
  milestone: NetworthMilestone
  accounts: NetworthAccounts
  bucket_labels: Record<string, string>
}

/** Bundled Net Worth pillar snapshot (Chunk 9.7) — hero donut, trend, milestone
 * and the CASH/PORTFOLIO accounts hierarchy in one round-trip. */
export function useNetworthSnapshot(period: NetworthPeriod) {
  return useQuery({
    queryKey: ["finance", "networth", "snapshot", period],
    queryFn: () => api.get<NetworthSnapshotResponse>(`/api/finance/networth/snapshot?period=${period}`),
    staleTime: 5 * 60_000,
  })
}
