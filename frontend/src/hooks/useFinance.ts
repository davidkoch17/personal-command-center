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

// --- Phase 15a: sophisticated finance layer (/api/finance/*) ----------------

export interface FinanceHolding {
  ticker: string
  name: string
  type: string | null
  bucket: string | null
  currency: string
  quantity: number
  avg_cost: number
  total_basis: number
  current_price: number | null
  market_value: number
  unrealized_pnl: number | null
  unrealized_pnl_pct: number | null
  sharpe: number | null
  volatility: number | null
  beta: number | null
  weight: number | null
}

export interface FinanceHoldingsResponse {
  holdings: FinanceHolding[]
  total_market_value: number
  count: number
}

interface BestWorst {
  period: string
  return: number
}

export interface FinancePerformanceResponse {
  period: string
  benchmark: string
  benchmark_name?: string
  available: boolean
  reason?: string
  time_weighted_return?: number | null
  money_weighted_return?: number | null
  annualized_return?: number | null
  alpha?: number | null
  beta?: number | null
  tracking_error?: number | null
  information_ratio?: number | null
  win_rate?: number | null
  best_worst?: Record<string, BestWorst | null>
  contribution?: {
    ticker: string
    weight: number
    position_return: number
    contribution: number
  }[]
}

export interface CumulativeResponse {
  period: string
  benchmark: string
  benchmark_name?: string
  series: { date: string; portfolio: number; benchmark: number }[]
}

export interface RollingResponse {
  window: number
  benchmark: string
  series: { date: string; sharpe: number | null; alpha: number | null; beta: number | null }[]
}

export interface RiskResponse {
  available: boolean
  reason?: string
  benchmark?: string
  volatility?: {
    rolling_30d: number | null
    rolling_90d: number | null
    rolling_12m: number | null
    annualized: number | null
  }
  sharpe?: number | null
  sortino?: number | null
  calmar?: number | null
  max_drawdown?: {
    magnitude: number | null
    peak_date: string | null
    trough_date: string | null
    recovery_date: string | null
    duration_days: number | null
  }
  beta?: number | null
  var?: Record<string, number | null>
  expected_shortfall?: Record<string, number | null>
  concentration?: {
    herfindahl_index: number | null
    effective_n_bets: number | null
    top_1_weight: number | null
    top_3_weight: number | null
    top_5_weight: number | null
  }
}

export interface CorrelationResponse {
  tickers: string[]
  matrix: Record<string, string | number>[]
}

export interface BucketRow {
  bucket: string
  label: string
  value: number
  current_weight: number
  target_weight: number
  drift: number
  status: "ok" | "warn" | "alert"
}

export interface BucketsResponse {
  total_value: number
  buckets: BucketRow[]
  unassigned: { ticker: string; value: number }[]
  alerts: { severity: string; bucket: string; message: string }[]
}

export interface TransactionRequest {
  date: string
  ticker: string
  action: "buy" | "sell" | "dividend" | "split" | "deposit" | "withdraw"
  quantity: number
  price: number
  currency?: string
  fees?: number
  notes?: string | null
}

export function useFinanceHoldings() {
  return useQuery({
    queryKey: ["finance", "holdings"],
    queryFn: () => api.get<FinanceHoldingsResponse>("/api/finance/holdings"),
  })
}

export function useFinancePerformance(period = "ytd", benchmark = "MSCI_WORLD") {
  return useQuery({
    queryKey: ["finance", "performance", period, benchmark],
    queryFn: () =>
      api.get<FinancePerformanceResponse>(
        `/api/finance/performance?period=${period}&benchmark=${benchmark}`,
      ),
  })
}

export function useFinanceCumulative(period = "1y", benchmark = "MSCI_WORLD") {
  return useQuery({
    queryKey: ["finance", "cumulative", period, benchmark],
    queryFn: () =>
      api.get<CumulativeResponse>(
        `/api/finance/performance/cumulative?period=${period}&benchmark=${benchmark}`,
      ),
  })
}

export function useFinanceRolling(window = 252, benchmark = "MSCI_WORLD") {
  return useQuery({
    queryKey: ["finance", "rolling", window, benchmark],
    queryFn: () =>
      api.get<RollingResponse>(
        `/api/finance/performance/rolling?window=${window}&benchmark=${benchmark}`,
      ),
  })
}

export function useFinanceRisk(benchmark = "MSCI_WORLD") {
  return useQuery({
    queryKey: ["finance", "risk", benchmark],
    queryFn: () => api.get<RiskResponse>(`/api/finance/risk?benchmark=${benchmark}`),
  })
}

export function useFinanceCorrelation() {
  return useQuery({
    queryKey: ["finance", "correlation"],
    queryFn: () => api.get<CorrelationResponse>("/api/finance/risk/correlation"),
  })
}

export function useBuckets() {
  return useQuery({
    queryKey: ["finance", "buckets"],
    queryFn: () => api.get<BucketsResponse>("/api/finance/buckets"),
  })
}

export function useRecordTransaction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: TransactionRequest) =>
      api.post<{ ok: boolean; ticker: string; action: string }>(
        "/api/finance/transactions",
        req,
      ),
    onSuccess: () => {
      // A new transaction changes holdings, buckets, performance + risk.
      qc.invalidateQueries({ queryKey: ["finance"] })
    },
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

// --- Phase 15b: optimization + factor analytics -----------------------------

type Weights = Record<string, number>

export interface OptPerformance {
  expected_return: number
  volatility: number
  sharpe: number
}

export interface OptPortfolio {
  weights: Weights
  performance: OptPerformance | null
}

export interface FrontierPoint {
  target_return: number
  risk: number
  return: number
  sharpe: number
  weights: Weights
}

export interface FrontierResponse {
  tickers: string[]
  points: FrontierPoint[]
  max_sharpe: OptPortfolio
  min_variance: OptPortfolio
  current: { return: number; risk: number; sharpe: number | null; weights: Weights } | null
}

export interface BLView {
  ticker: string
  expected_return: number
  confidence: number
  derived: boolean
  label: string
}

export interface BlackLittermanResponse {
  tickers: string[]
  auto_views: boolean
  weights: Weights
  performance: OptPerformance | null
  posterior_returns?: Weights
  market_equilibrium?: Weights
  views_used: BLView[]
}

export interface OptSignalsResponse {
  available: boolean
  reason?: string
  current_sharpe?: number | null
  max_sharpe?: number | null
  sharpe_gap?: number | null
  current_effective_bets?: number | null
  min_variance_effective_bets?: number | null
  max_sharpe_weights?: Weights
}

export interface FF3Response {
  available: boolean
  reason?: string
  region?: string
  alpha_monthly?: number
  alpha_annual?: number
  beta_mkt?: number
  beta_smb?: number
  beta_hml?: number
  t_alpha?: number
  t_mkt?: number
  t_smb?: number
  t_hml?: number
  r_squared?: number
  n_observations?: number
}

export interface DecompositionResponse {
  available: boolean
  reason?: string
  region?: string
  regression?: FF3Response
  variance_decomposition?: {
    market: number
    size_smb: number
    value_hml: number
    idiosyncratic: number
  }
}

export function useOptFrontier(nPoints = 50) {
  return useQuery({
    queryKey: ["finance", "frontier", nPoints],
    queryFn: () =>
      api.get<FrontierResponse>(`/api/finance/optimization/frontier?n_points=${nPoints}`),
  })
}

export function useOptMaxSharpe() {
  return useQuery({
    queryKey: ["finance", "max-sharpe"],
    queryFn: () => api.get<OptPortfolio & { tickers: string[] }>("/api/finance/optimization/max-sharpe"),
  })
}

export function useOptMinVariance() {
  return useQuery({
    queryKey: ["finance", "min-variance"],
    queryFn: () => api.get<OptPortfolio & { tickers: string[] }>("/api/finance/optimization/min-variance"),
  })
}

export function useOptRiskParity() {
  return useQuery({
    queryKey: ["finance", "risk-parity"],
    queryFn: () => api.get<{ tickers: string[]; weights: Weights }>("/api/finance/optimization/risk-parity"),
  })
}

export function useBlackLitterman() {
  return useQuery({
    queryKey: ["finance", "black-litterman"],
    queryFn: () =>
      api.post<BlackLittermanResponse>("/api/finance/optimization/black-litterman", {}),
  })
}

export function useOptSignals() {
  return useQuery({
    queryKey: ["finance", "opt-signals"],
    queryFn: () => api.get<OptSignalsResponse>("/api/finance/optimization/signals"),
  })
}

export function useFF3(region = "US") {
  return useQuery({
    queryKey: ["finance", "ff3", region],
    queryFn: () => api.get<FF3Response>(`/api/finance/factors/ff3?region=${region}`),
  })
}

export function useFactorDecomposition(region = "US") {
  return useQuery({
    queryKey: ["finance", "factor-decomposition", region],
    queryFn: () =>
      api.get<DecompositionResponse>(`/api/finance/factors/decomposition?region=${region}`),
  })
}
