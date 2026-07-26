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
  /** Ordered tier + theme-section structure parsed from Watchlist.md. */
  sections: WatchlistSection[]
  /** Backward-compatible flat map by tier (used by the tier filter + macro tab). */
  tiers: Record<string, WatchlistEntry[]>
  count: number
  /** Append targets for the add dialog (Ad-hoc first). */
  form_sections: FormSection[]
  source: string
}

export interface WatchlistSection {
  key: string
  tier: string
  letter: string
  title: string
  entries: WatchlistEntry[]
}

export interface FormSection {
  key: string
  label: string
}

export interface WatchlistEntry {
  ticker: string
  name: string
  status: string
  tier: string
  section?: string
  section_title?: string
  letter?: string
  is_ticker?: boolean
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
    // Holdings carry per-position price + risk (network-heavy); 5 min is plenty.
    staleTime: 5 * 60_000,
  })
}

// Phase 15e staleTime tiers (Section 3.3): price/perf/risk are network-heavy and
// change slowly intraday → 5 min; factor regressions → 24 h; FX → 1 h.
const STALE = {
  positions: 30_000,
  price: 5 * 60_000,
  performance: 5 * 60_000,
  factors: 24 * 60 * 60_000,
  fx: 60 * 60_000,
} as const

export function useFinancePerformance(period = "ytd", benchmark = "MSCI_WORLD") {
  return useQuery({
    queryKey: ["finance", "performance", period, benchmark],
    queryFn: () =>
      api.get<FinancePerformanceResponse>(
        `/api/finance/performance?period=${period}&benchmark=${benchmark}`,
      ),
    staleTime: STALE.performance,
  })
}

export function useFinanceCumulative(period = "1y", benchmark = "MSCI_WORLD") {
  return useQuery({
    queryKey: ["finance", "cumulative", period, benchmark],
    queryFn: () =>
      api.get<CumulativeResponse>(
        `/api/finance/performance/cumulative?period=${period}&benchmark=${benchmark}`,
      ),
    staleTime: STALE.performance,
  })
}

export function useFinanceRolling(window = 252, benchmark = "MSCI_WORLD") {
  return useQuery({
    queryKey: ["finance", "rolling", window, benchmark],
    queryFn: () =>
      api.get<RollingResponse>(
        `/api/finance/performance/rolling?window=${window}&benchmark=${benchmark}`,
      ),
    staleTime: STALE.performance,
  })
}

export function useFinanceRisk(benchmark = "MSCI_WORLD") {
  return useQuery({
    queryKey: ["finance", "risk", benchmark],
    queryFn: () => api.get<RiskResponse>(`/api/finance/risk?benchmark=${benchmark}`),
    staleTime: STALE.performance,
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

export interface MonthlyReportIncome {
  salary: number
  other: number
  total: number
}

export interface MonthlyReportCategory {
  category: string
  amount: number
}

export interface MonthlyReportTransaction {
  date: string
  description: string
  amount: number
  category: string
  card: string
  notes: string
}

export interface MonthlyReportResponse {
  month: string
  income: MonthlyReportIncome
  expenses: { by_category: MonthlyReportCategory[]; total: number }
  net: number
  savings_rate: number | null
  transactions: MonthlyReportTransaction[]
}

export function useMoneyAvailableMonths() {
  return useQuery({
    queryKey: ["money", "available-months"],
    queryFn: () => api.get<{ months: string[] }>("/api/money/available-months"),
    staleTime: 60_000,
  })
}

export function useMoneyReport(month: string | null) {
  return useQuery({
    queryKey: ["money", "report", month],
    queryFn: () => api.get<MonthlyReportResponse>(`/api/money/report/${month}`),
    enabled: !!month,
    staleTime: 30_000,
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

// --- Reserve & allocation (surplus split, TR contribution tracking) --------

export interface AllocationReserveStatus {
  month: string
  reserve_balance: number | null
  target: number
  percent_filled: number | null
  remaining_to_target: number | null
}

export interface AllocationSplitRecommendation {
  to_reserve: number
  to_invest: number
}

export interface ContributionEstimate {
  value: number | null
  reliable: boolean
  flags: string[]
  depot_value_change: number | null
  market_pnl: number | null
}

export interface ActualContribution {
  month: string
  value: number | null
  source: "explicit_deposits" | "manual_override" | "estimated" | null
  reliable: boolean
  flags: string[]
  estimate: ContributionEstimate
}

export interface MoneyAllocationResponse {
  month: string
  income_by_type: Record<string, number>
  investable_income: number
  expenses: { by_category: MonthlyReportCategory[]; total: number }
  investable_surplus: number
  savings_rate: number | null
  reserve: AllocationReserveStatus
  split_recommendation: AllocationSplitRecommendation
  // Dependent on the TR statement parser being verified — value/source may be
  // null (see ActualContribution.flags) until then, or until an override is set.
  actual_contribution: ActualContribution
  contribution_vs_recommended: number | null
}

export function useMoneyAllocation(month: string | null) {
  return useQuery({
    queryKey: ["money", "allocation", month],
    queryFn: () => api.get<MoneyAllocationResponse>(`/api/money/allocation/${month}`),
    enabled: !!month,
    staleTime: 30_000,
  })
}

export function useSetContributionOverride() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ month, value }: { month: string; value: number | null }) =>
      api.post<{ ok: boolean; month: string; value: number | null }>(
        `/api/money/allocation/${month}/contribution-override`,
        { value },
      ),
    onSuccess: (_data, variables) =>
      qc.invalidateQueries({ queryKey: ["money", "allocation", variables.month] }),
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
    staleTime: STALE.factors,
  })
}

export function useFactorDecomposition(region = "US") {
  return useQuery({
    queryKey: ["finance", "factor-decomposition", region],
    queryFn: () =>
      api.get<DecompositionResponse>(`/api/finance/factors/decomposition?region=${region}`),
    staleTime: STALE.factors,
  })
}

// --- Phase 15e: FF5 + Carhart momentum factor models ------------------------

export interface FF5Response {
  available: boolean
  reason?: string
  region?: string
  model?: string
  alpha_monthly?: number
  alpha_annual?: number
  t_alpha?: number
  r_squared?: number
  n_observations?: number
  betas?: Record<string, number>
  t_stats?: Record<string, number>
}

export interface MomentumResponse extends FF5Response {
  beta_umd?: number
  t_umd?: number
}

export function useFF5(region = "US") {
  return useQuery({
    queryKey: ["finance", "ff5", region],
    queryFn: () => api.get<FF5Response>(`/api/finance/factors/ff5?region=${region}`),
    staleTime: STALE.factors,
  })
}

export function useMomentumFactor(region = "US") {
  return useQuery({
    queryKey: ["finance", "momentum", region],
    queryFn: () => api.get<MomentumResponse>(`/api/finance/factors/momentum?region=${region}`),
    staleTime: STALE.factors,
  })
}

// --- Phase 15c: decision support + backtesting ------------------------------

export interface SizeResponse {
  portfolio_value: number
  conviction_score: number
  weight_pct: number
  eur_amount: number
  can_enter: boolean
  rationale: string
}

export interface BucketAlloc {
  value: number
  weight: number
  target: number
  drift: number
}

export interface RebalanceRec {
  bucket: string
  action: string
  current_weight?: number
  target_weight?: number
  drift_pct?: number
  delta_eur: number
  priority: string
  rationale: string
}

export interface RebalanceResponse {
  portfolio_value: number
  allocations: Record<string, BucketAlloc>
  recommendations: RebalanceRec[]
  drift_tolerance: number
}

export interface HarvestCandidate {
  ticker: string
  unrealized_pnl: number
  unrealized_pnl_pct: number
  holding_days: number
  type: string | null
  tax_savings_estimate: number
  warning: string | null
}

export interface HarvestResponse {
  candidates: HarvestCandidate[]
  count: number
}

export interface ConcentrationAlert {
  type: string
  ticker: string
  weight: number
  rationale: string
  severity: string
}

export interface AlertsResponse {
  alerts: ConcentrationAlert[]
  count: number
}

export interface HypothesesViewResponse {
  views: BLView[]
  aggregate_expected_return: number | null
  n_views: number
}

export interface DecisionSummaryResponse {
  portfolio_value: number
  rebalance_count: number
  rebalance_high: number
  concentration_count: number
  concentration_high: number
  harvest_count: number
  harvest_savings: number
}

export interface WhatIfResponse {
  ticker?: string
  action?: string
  action_date?: string
  initial_price?: number
  current_price?: number
  qty?: number
  counterfactual_pnl?: number
  cumulative_return_pct?: number
  error?: string
}

export interface ShockPosition {
  beta?: number
  value?: number
  impact?: number
  error?: string
}

export interface MarketShockResponse {
  shock_pct: number
  total_value: number
  total_estimated_impact: number
  impact_pct: number | null
  per_position: Record<string, ShockPosition>
}

export interface FxAffected {
  currency?: string
  value?: number
  impact?: number
  error?: string
}

export interface FxShockResponse {
  currency: string
  shock_pct: number
  total_impact: number
  total_exposure: number
  affected: Record<string, FxAffected>
}

export function useDecisionRebalance() {
  return useQuery({
    queryKey: ["finance", "decisions", "rebalance"],
    queryFn: () => api.get<RebalanceResponse>("/api/finance/decisions/rebalance"),
  })
}

export function useDecisionHarvest() {
  return useQuery({
    queryKey: ["finance", "decisions", "harvest"],
    queryFn: () => api.get<HarvestResponse>("/api/finance/decisions/harvest"),
  })
}

export function useDecisionAlerts() {
  return useQuery({
    queryKey: ["finance", "decisions", "alerts"],
    queryFn: () => api.get<AlertsResponse>("/api/finance/decisions/alerts"),
  })
}

export function useDecisionHypothesesView() {
  return useQuery({
    queryKey: ["finance", "decisions", "hypotheses-view"],
    queryFn: () => api.get<HypothesesViewResponse>("/api/finance/decisions/hypotheses-view"),
  })
}

export function useDecisionSummary() {
  return useQuery({
    queryKey: ["finance", "decisions", "summary"],
    queryFn: () => api.get<DecisionSummaryResponse>("/api/finance/decisions/summary"),
  })
}

export function useSuggestSize() {
  return useMutation({
    mutationFn: (conviction_score: number) =>
      api.post<SizeResponse>("/api/finance/decisions/size", { conviction_score }),
  })
}

export function useMarketShock() {
  return useMutation({
    mutationFn: (shock_pct: number) =>
      api.post<MarketShockResponse>("/api/finance/backtest/market-shock", { shock_pct }),
  })
}

export function useFxShock() {
  return useMutation({
    mutationFn: (req: { currency: string; shock_pct: number }) =>
      api.post<FxShockResponse>("/api/finance/backtest/fx-shock", req),
  })
}

export function useWhatIf() {
  return useMutation({
    mutationFn: (req: { ticker: string; action: string; qty: number; date: string }) =>
      api.post<WhatIfResponse>("/api/finance/backtest/what-if", req),
  })
}

// --- Phase 15d: behavioral journal + watchlist + money integration ----------

export interface DecisionSummaryRow {
  filename: string
  date: string
  ticker: string | null
  action: string | null
  conviction: number | null
  emotion: string | null
  has_retrospective: boolean
  path: string
}

export interface DecisionsResponse {
  decisions: DecisionSummaryRow[]
  count: number
}

export interface DecisionDetail extends Partial<DecisionSummaryRow> {
  filename: string
  content: string
}

export interface LogDecisionRequest {
  ticker: string
  action: string
  quantity: number
  price: number
  rationale: string
  conviction_score: number
  emotion: string
  expected_return?: number | null
  expected_timeframe_months?: number | null
  thesis?: string
  risks?: string
  pre_mortem?: string
}

export interface HitRateResponse {
  hypotheses_reviewed: number
  confirmed: number
  weakened: number
  hit_rate: number | null
  details: { ticker: string; status: string; raw: string }[]
  quarters_back: number
}

export interface AntiPortfolioEntry {
  considered_date: string
  ticker: string
  name: string
  price: number | null
  reason: string | null
  months_ago?: number
}

export interface AntiPortfolioResponse {
  skips: AntiPortfolioEntry[]
  count: number
  review_due: AntiPortfolioEntry[]
}

export interface WatchlistMetric {
  ticker: string
  sharpe?: number | null
  volatility?: number | null
  beta?: number | null
  max_drawdown?: number | null
  momentum_3m?: number | null
  momentum_12m?: number | null
  error?: string
}

export interface WatchlistMetricsResponse {
  metrics: WatchlistMetric[]
  count: number
  beta_benchmark: string
}

export interface SimulateAddResponse {
  new_ticker: string
  weight: number
  available: boolean
  reason?: string
  before?: { sharpe: number | null; volatility: number | null; beta: number | null }
  after?: { sharpe: number | null; volatility: number | null; beta: number | null }
  modeled_metrics?: {
    delta_sharpe: number | null
    delta_volatility: number | null
    delta_beta: number | null
    correlation_to_portfolio: number
  }
}

export interface AnnualTaxRequest {
  realized_gains: number
  dividends?: number
  church_tax?: boolean
}

export interface AnnualTaxResponse {
  realized_gains: number
  dividends: number
  sparerpauschbetrag: number
  sparerpauschbetrag_used: number
  taxable_base: number
  tax_owed: number
  effective_rate: number
}

export interface HoldingPeriodResponse {
  ticker: string
  available: boolean
  reason?: string
  type?: string | null
  is_crypto?: boolean | null
  earliest_buy_date?: string
  days_held?: number
  days_to_tax_free?: number
  is_tax_free?: boolean
  tax_free_date?: string
}

export interface CapitalAllocationSuggestion {
  bucket: string
  label: string
  current_weight: number
  target_weight: number
  drift_pct: number
  current_value: number
  suggested_deploy_eur: number
  rationale: string
}

export interface CapitalAllocationResponse {
  cash_deployable: number
  portfolio_value: number
  new_total: number
  suggestions: CapitalAllocationSuggestion[]
}

export function useDecisions(limit = 50) {
  return useQuery({
    queryKey: ["finance", "journal", "decisions", limit],
    queryFn: () => api.get<DecisionsResponse>(`/api/finance/journal/decisions?limit=${limit}`),
  })
}

export function useDecision(filename: string | undefined) {
  return useQuery({
    queryKey: ["finance", "journal", "decision", filename],
    queryFn: () =>
      api.get<DecisionDetail>(`/api/finance/journal/decision/${encodeURIComponent(filename!)}`),
    enabled: !!filename,
  })
}

export function useLogDecision() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: LogDecisionRequest) =>
      api.post<{ ok: boolean; filename: string }>("/api/finance/journal/decision", req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "journal"] }),
  })
}

export function useAddRetrospective() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: { filename: string; retro_text: string; was_right: boolean }) =>
      api.post<{ ok: boolean; filename: string }>(
        `/api/finance/journal/${encodeURIComponent(req.filename)}/retrospective`,
        { retro_text: req.retro_text, was_right: req.was_right },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "journal"] }),
  })
}

export function useHitRate(quartersBack = 4) {
  return useQuery({
    queryKey: ["finance", "journal", "hit-rate", quartersBack],
    queryFn: () =>
      api.get<HitRateResponse>(`/api/finance/journal/hit-rate?quarters_back=${quartersBack}`),
  })
}

export function useAntiPortfolio() {
  return useQuery({
    queryKey: ["finance", "journal", "anti-portfolio"],
    queryFn: () => api.get<AntiPortfolioResponse>("/api/finance/journal/anti-portfolio"),
  })
}

export function useWatchlistMetrics() {
  return useQuery({
    queryKey: ["finance", "watchlist", "metrics"],
    queryFn: () => api.get<WatchlistMetricsResponse>("/api/finance/watchlist/metrics"),
    staleTime: 5 * 60_000, // network-heavy; cache for 5 min
  })
}

export function useSimulateAdd() {
  return useMutation({
    mutationFn: (req: { ticker: string; weight: number }) =>
      api.post<SimulateAddResponse>("/api/finance/watchlist/simulate-add", req),
  })
}

export function useAnnualTaxEstimate() {
  return useMutation({
    mutationFn: (req: AnnualTaxRequest) =>
      api.post<AnnualTaxResponse>("/api/finance/tax/annual-estimate", req),
  })
}

export function useHoldingPeriod(ticker: string | undefined) {
  return useQuery({
    queryKey: ["finance", "tax", "holding-period", ticker],
    queryFn: () =>
      api.get<HoldingPeriodResponse>(`/api/finance/tax/holding-period/${encodeURIComponent(ticker!)}`),
    enabled: !!ticker,
  })
}

/** Holding-period (Spekulationsfrist) status for every held crypto ticker.
 *  Drives the Home "next tax-free" nudge and the Money tax tab. */
export function useCryptoHoldingPeriods() {
  const holdings = useFinanceHoldings()
  const cryptoTickers = (holdings.data?.holdings ?? [])
    .filter((h) => h.type === "crypto")
    .map((h) => h.ticker)
  const results = useQueries({
    queries: cryptoTickers.map((t) => ({
      queryKey: ["finance", "tax", "holding-period", t],
      queryFn: () =>
        api.get<HoldingPeriodResponse>(`/api/finance/tax/holding-period/${encodeURIComponent(t)}`),
      enabled: !!t,
      staleTime: 60 * 60_000,
    })),
  })
  return {
    isLoading: holdings.isLoading || results.some((r) => r.isLoading),
    data: results.map((r) => r.data).filter(Boolean) as HoldingPeriodResponse[],
  }
}

export function useCapitalAllocation(cash?: number) {
  return useQuery({
    queryKey: ["finance", "capital-allocation", cash ?? "auto"],
    queryFn: () =>
      api.get<CapitalAllocationResponse>(
        `/api/finance/capital-allocation/suggest${cash != null ? `?cash=${cash}` : ""}`,
      ),
  })
}

// --- Phase 15e: currency, attribution, stress tests, diagnostics ------------

export interface CurrencyBreakdownResponse {
  reporting_currency: string
  total_value: number
  by_currency: Record<string, { value: number; weight: number }>
  fx_missing: string[]
}

export interface HedgedUnhedged {
  available: boolean
  reason?: string
  reporting_currency?: string
  hedged_return?: number
  unhedged_return?: number
  currency_contribution?: number
  note?: string
}

export interface CurrencyPerformanceResponse {
  period: string
  currency: string
  available: boolean
  reason?: string
  time_weighted_return?: number | null
  annualized_return?: number | null
  volatility?: number | null
  hedged_vs_unhedged?: HedgedUnhedged
}

export function useCurrencyBreakdown(currency = "EUR") {
  return useQuery({
    queryKey: ["finance", "currency", "breakdown", currency],
    queryFn: () =>
      api.get<CurrencyBreakdownResponse>(`/api/finance/currency/breakdown?currency=${currency}`),
    staleTime: 60 * 60_000, // FX tier
  })
}

export function useCurrencyPerformance(period = "ytd", currency = "EUR") {
  return useQuery({
    queryKey: ["finance", "currency", "performance", period, currency],
    queryFn: () =>
      api.get<CurrencyPerformanceResponse>(
        `/api/finance/currency/performance?period=${period}&currency=${currency}`,
      ),
    staleTime: 5 * 60_000,
  })
}

export function useFxRate(from: string, to: string) {
  return useQuery({
    queryKey: ["finance", "fx", from, to],
    queryFn: () =>
      api.get<{ from: string; to: string; rate: number | null; available: boolean }>(
        `/api/finance/currency/fx/${from}/${to}`,
      ),
    staleTime: 60 * 60_000,
  })
}

export interface BrinsonSegment {
  portfolio_weight: number
  benchmark_weight: number
  portfolio_return: number
  benchmark_return: number
  allocation: number
  selection: number
  interaction: number
  total: number
}

export interface BrinsonResponse {
  available: boolean
  reason?: string
  period?: string
  per_segment?: Record<string, BrinsonSegment>
  labels?: Record<string, string>
  allocation_effect?: number
  selection_effect?: number
  interaction_effect?: number
  total_excess_return?: number
}

export function useBrinson(period = "ytd") {
  return useQuery({
    queryKey: ["finance", "attribution", "brinson", period],
    queryFn: () => api.get<BrinsonResponse>(`/api/finance/attribution/brinson?period=${period}`),
    staleTime: 5 * 60_000,
  })
}

export interface StressPosition {
  value?: number
  shock_return?: number
  impact?: number
  estimated?: boolean
  error?: string
}

export interface StressReplayResponse {
  available: boolean
  reason?: string
  shock?: string
  label?: string
  start?: string
  end?: string
  benchmark?: string
  benchmark_return?: number | null
  total_value?: number
  total_estimated_impact?: number
  impact_pct?: number | null
  per_position?: Record<string, StressPosition>
}

export function useStressReplayAll() {
  return useQuery({
    queryKey: ["finance", "stress", "replay-all"],
    queryFn: () => api.get<Record<string, StressReplayResponse>>("/api/finance/stress/replay-all"),
    staleTime: 24 * 60 * 60_000, // historical windows never change
  })
}

export interface FinanceDiagnosticsResponse {
  checks: { name: string; status: string; detail?: string }[]
}

export function useFinanceDiagnostics(enabled: boolean, probe = false) {
  return useQuery({
    queryKey: ["finance", "diagnostics", probe],
    queryFn: () =>
      api.get<FinanceDiagnosticsResponse>(`/api/finance/diagnostics?probe=${probe}`),
    enabled,
    staleTime: 0,
  })
}

// --- v2 Wealth page: net-worth trend (N1) + after-tax-return (D2) + config ---

export interface NetWorthPoint {
  month: string
  total: number | null
  source: string
}

export interface NetWorthHistoryResponse {
  history: NetWorthPoint[]
  count: number
  latest: NetWorthPoint | null
  change_since_start: number | null
}

/** Monthly net-worth trend (N1) — sheet backbone overlaid with live snapshots. */
export function useNetWorthHistory() {
  return useQuery({
    queryKey: ["money", "networth-history"],
    queryFn: () => api.get<NetWorthHistoryResponse>("/api/money/networth-history"),
    staleTime: 5 * 60_000,
  })
}

export interface AfterTaxReturnResponse {
  gross_return: number
  after_tax_return: number
  asset_type: string
  holding_period_days: number
  tax_free: boolean
  effective_rate: number
}

/** After-tax return (D2) — wires the built-but-unused tax/after-tax-return GET. */
export function useAfterTaxReturn() {
  return useMutation({
    mutationFn: (req: {
      gross_return: number
      holding_period_days: number
      asset_type: string
      church_tax?: boolean
    }) =>
      api.get<AfterTaxReturnResponse>(
        `/api/finance/tax/after-tax-return?gross_return=${req.gross_return}` +
          `&holding_period_days=${req.holding_period_days}` +
          `&asset_type=${encodeURIComponent(req.asset_type)}` +
          `&church_tax=${req.church_tax ? "true" : "false"}`,
      ),
  })
}

export interface InsuranceEntry {
  key: string
  type: string
  status: string
  provider: string | null
  monthly_eur: number | null
  notes: string | null
}

export interface PkvDecision {
  status: string
  decided_on: string | null
  outcome: string | null
  rationale: string | null
  notes: string | null
}

export interface AccountEntry {
  key: string
  label: string
  bank: string | null
  purpose: string
}

export interface WealthConfigResponse {
  insurance: InsuranceEntry[]
  pkv_decision: PkvDecision
  accounts: AccountEntry[]
  source: string
}

/** Insurance tracker + PKV record + Mehrkontenmodell (structural template). */
export function useWealthConfig() {
  return useQuery({
    queryKey: ["money", "wealth-config"],
    queryFn: () => api.get<WealthConfigResponse>("/api/money/wealth-config"),
    staleTime: 60 * 60_000,
  })
}
