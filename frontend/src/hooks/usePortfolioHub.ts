/**
 * Phase D — Portfolio Hub data hooks.
 *
 * Wraps the new backend endpoints for the Portfolio-Hub tabs:
 * - Overview   : net-worth daily series + this-month decomposition
 * - Holdings   : per-position period P&L + realized trade log
 * - Watchlist  : Connected News (captures per ticker) + sector radar + plan card
 * - Captures   : captures list / detail / routing
 * - Research   : reports library + run launcher + hypotheses
 * - Portfolio  : KPI-band summary + indexed performance chart (Chunk 2)
 * - Stock      : Single Stock tab — universe / detail / peers (Chunk 4)
 *
 * Decision-alerts (Overview + Portfolio strips) reuse `useDecisionSummary`
 * from useFinance; the Decision Log (Research tab) reuses `useDecisions` /
 * `useLogDecision`.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

// --- Overview ---------------------------------------------------------------

export interface NetWorthDailyPoint {
  date: string
  net_worth_eur: number
  bank_total: number
  portfolio_total_eur: number
  crypto_total_eur: number
}

export function useNetWorthDaily(days = 90) {
  return useQuery({
    queryKey: ["hub", "networth-daily", days],
    queryFn: () =>
      api.get<{ series: NetWorthDailyPoint[]; count: number; days: number }>(
        `/api/finance/networth/daily?days=${days}`,
      ),
    staleTime: 5 * 60_000,
  })
}

export interface DecompositionResponse {
  available: boolean
  reason?: string
  month?: string
  baseline_date?: string
  as_of?: string
  net_worth_now?: number
  net_worth_start?: number
  mom_delta?: number
  savings?: number
  savings_source?: string
  investments?: number
  net_contributions?: number
  residual?: number
  bank_change?: number
}

export function useNetWorthDecomposition() {
  return useQuery({
    queryKey: ["hub", "networth-decomposition"],
    queryFn: () => api.get<DecompositionResponse>("/api/finance/networth/decomposition"),
    staleTime: 5 * 60_000,
  })
}

export interface BridgeResponse {
  available: boolean
  reason?: string
  month: string
  opening_date?: string
  closing_date?: string
  opening_net_worth?: number
  income?: number | null
  expenses?: number | null
  savings?: number
  savings_source?: string
  contributions?: number
  market_pnl?: number
  closing_net_worth?: number
  mom_delta?: number
  residual?: number
}

export function useNetWorthBridge(month: string | null) {
  return useQuery({
    queryKey: ["hub", "networth-bridge", month],
    queryFn: () => api.get<BridgeResponse>(`/api/finance/networth/bridge${month ? `?month=${month}` : ""}`),
    enabled: !!month,
    staleTime: 5 * 60_000,
  })
}

// --- Holdings ---------------------------------------------------------------

export interface PnlPosition {
  ticker: string
  name: string
  type: string | null
  bucket: string
  bucket_source: "override" | "map" | "unassigned"
  qty: number
  price_eur: number | null
  value_eur: number
  cost_basis_eur: number
  weight: number | null
  pnl_all: number
  pnl_all_pct: number | null
  pnl_month: number
  pnl_month_pct: number | null
  pnl_ytd: number
  pnl_ytd_pct: number | null
}

export interface HoldingsPnlResponse {
  positions: PnlPosition[]
  count: number
  total_value: number
  pnl_month_total: number
  pnl_ytd_total: number
  pnl_all_total: number
  as_of: string
}

export function useHoldingsPnl() {
  return useQuery({
    queryKey: ["hub", "holdings-pnl"],
    queryFn: () => api.get<HoldingsPnlResponse>("/api/finance/holdings/pnl"),
    staleTime: 60_000,
  })
}

export interface RealizedTrade {
  ticker: string
  date_bought: string
  date_sold: string
  qty: number
  buy_price_eur: number
  sell_price_eur: number
  fees_eur: number
  realized_gain_eur: number
  holding_days: number
}

export interface RealizedTradesResponse {
  trades: RealizedTrade[]
  count: number
  ytd_realized_eur: number
  year: number
}

export function useRealizedTrades() {
  return useQuery({
    queryKey: ["hub", "realized-trades"],
    queryFn: () => api.get<RealizedTradesResponse>("/api/finance/trades/realized"),
    staleTime: 60_000,
  })
}

// --- Captures ---------------------------------------------------------------

export interface CaptureTicker {
  ticker: string
  sector: string | null
}

export interface Capture {
  id: string
  captured_at: string | null
  type: string | null
  topic_tag: string | null
  topic_slug: string | null
  ocr_text: string | null
  voice_transcript: string | null
  source_hint: string | null
  ai_tags: string[] | string | null
  routing_suggestions: unknown
  routing_locked: number
  category: string | null
  status: string | null
  image_path: string | null
  voice_path: string | null
  notes: string | null
  processed_at: string | null
  tickers: CaptureTicker[]
  link_sector?: string | null
}

export interface CapturesResponse {
  captures: Capture[]
  count: number
  status_counts: Record<string, number>
}

export function useCaptures(status?: string, category?: string) {
  const params = new URLSearchParams()
  if (status) params.set("status", status)
  if (category) params.set("category", category)
  const qs = params.toString()
  return useQuery({
    queryKey: ["hub", "captures", status ?? "all", category ?? "all"],
    queryFn: () => api.get<CapturesResponse>(`/api/captures${qs ? `?${qs}` : ""}`),
    staleTime: 30_000,
  })
}

export interface BigMove {
  type: "day_move" | "cluster"
  message: string
  value: number
}

export interface ConnectedNewsResponse {
  ticker: string
  sectors: { sector: string; count: number }[]
  big_moves: BigMove[]
  day_change_pct: number | null
  captures: Capture[]
  count: number
}

export function useConnectedNews(ticker: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ["hub", "connected-news", ticker],
    queryFn: () =>
      api.get<ConnectedNewsResponse>(`/api/captures/for-ticker/${encodeURIComponent(ticker!)}`),
    enabled: enabled && !!ticker,
    staleTime: 60_000,
  })
}

export interface RadarResponse {
  sectors: { sector: string; count: number }[]
  ticker_counts: Record<string, number>
}

export function useCaptureRadar() {
  return useQuery({
    queryKey: ["hub", "capture-radar"],
    queryFn: () => api.get<RadarResponse>("/api/captures/radar"),
    staleTime: 60_000,
  })
}

export interface RouteCaptureRequest {
  category?: string
  status?: string
  tickers?: CaptureTicker[]
  notes?: string
  approve?: boolean
  task_text?: string
  project?: string
  title?: string
}

export function useRouteCapture() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, req }: { id: string; req: RouteCaptureRequest }) =>
      api.post<{ ok: boolean; capture_id: string; status: string; routed: unknown }>(
        `/api/captures/${encodeURIComponent(id)}/route`,
        req,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hub", "captures"] })
      qc.invalidateQueries({ queryKey: ["hub", "capture-radar"] })
      qc.invalidateQueries({ queryKey: ["hub", "connected-news"] })
    },
  })
}

// --- Research ---------------------------------------------------------------

/** A report sidecar (Phase C schema). Only the dashboard-critical keys are typed;
 *  the rest pass through (skills carry skill-specific extras). */
export interface ReportSidecar {
  ticker?: string | null
  company?: string | null
  exchange?: string | null
  analysis_date?: string
  currency?: string | null
  current_price_at_analysis?: number | null
  market_cap?: string | null
  horizon?: string | null
  recommendation?: string | null
  fair_value_low?: number | null
  fair_value_high?: number | null
  upside_low_pct?: number | null
  upside_high_pct?: number | null
  thesis_oneliner?: string | null
  scenarios?: Record<string, { prob?: number; implied_value?: number; implied_value_eur?: number; note?: string }>
  // EUR-display layer (Phase H): backend converts native valuation fields at
  // current FX so Portfolio stays EUR-everywhere. Absent if FX was unavailable.
  native_currency?: string | null
  display_currency?: string | null
  fx_to_eur?: number | null
  fx_stale?: boolean
  live_price_eur?: number | null
  fair_value_low_eur?: number | null
  fair_value_high_eur?: number | null
  current_price_at_analysis_eur?: number | null
  upside_low_pct_eur?: number | null
  upside_high_pct_eur?: number | null
  monitorables?: string[]
  thesis_break_triggers?: string[]
  catalysts?: { label: string; date?: string }[]
  report_path?: string
  sources_as_of?: string
  skill?: string
  skill_label?: string
  target?: string
  generated_at?: string
  sidecar_path?: string
  [key: string]: unknown
}

export function useReports() {
  return useQuery({
    queryKey: ["hub", "reports"],
    queryFn: () => api.get<{ reports: ReportSidecar[]; count: number }>("/api/research/reports"),
    staleTime: 60_000,
  })
}

export function useLatestReport(ticker: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ["hub", "latest-report", ticker],
    queryFn: () =>
      api.get<{ ticker: string; report: ReportSidecar | null }>(
        `/api/research/reports/latest/${encodeURIComponent(ticker!)}`,
      ),
    enabled: enabled && !!ticker,
    staleTime: 60_000,
  })
}

export interface ResearchSkillMeta {
  key: string
  label: string
  target_kind: string
}

export function useResearchSkills() {
  return useQuery({
    queryKey: ["hub", "research-skills"],
    queryFn: () => api.get<{ skills: ResearchSkillMeta[] }>("/api/research/skills"),
    staleTime: 60 * 60_000,
  })
}

export function useRunResearch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: { skill: string; target?: string; extra?: string }) =>
      api.post<{ ok: boolean; run_id: string; skill: string; target: string | null }>(
        "/api/research/run",
        req,
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  })
}

export function useHypotheses() {
  return useQuery({
    queryKey: ["hub", "hypotheses"],
    queryFn: () =>
      api.get<{ hypotheses: { text: string }[]; count: number; source: string | null }>(
        "/api/research/hypotheses",
      ),
    staleTime: 60_000,
  })
}

// --- Portfolio (Chunk 2) -----------------------------------------------------

export interface DashboardTopHolding {
  ticker: string
  name: string
  bucket: string
  bucket_source: "override" | "map" | "unassigned"
  value_eur: number
  day_change_pct: number | null
  day_change_eur: number | null
  weight: number | null
}

export interface DashboardBucketDrift {
  bucket: string
  label: string
  value: number
  current_weight: number
  target_weight: number
  drift: number
  status: "ok" | "warn" | "alert"
}

export interface DashboardSummaryResponse {
  available: boolean
  benchmark: string
  benchmark_name: string
  portfolio_value_eur: number
  day_change_eur: number | null
  day_change_pct: number | null
  ytd_return_pct: number | null
  ytd_return_eur: number | null
  benchmark_ytd_return_pct: number | null
  sharpe_1y: number | null
  benchmark_sharpe_1y: number | null
  worst_drift_bucket: DashboardBucketDrift | null
  top_holdings: DashboardTopHolding[]
  holdings_count: number
}

/** KPI band + top-5 holdings — one round trip for the Portfolio tab's first paint. */
export function useDashboardSummary(benchmark: string) {
  return useQuery({
    queryKey: ["hub", "dashboard-summary", benchmark],
    queryFn: () => api.get<DashboardSummaryResponse>(`/api/finance/dashboard/summary?benchmark=${benchmark}`),
    staleTime: 60_000,
  })
}

export interface DashboardIndexedPoint {
  date: string
  portfolio: number
  benchmark: number
}

export interface DashboardPerformanceResponse {
  available: boolean
  reason?: string
  period: string
  benchmark: string
  benchmark_name?: string
  series: DashboardIndexedPoint[]
}

/** Portfolio-tab performance chart: portfolio + benchmark indexed to 100. */
export function useDashboardPerformance(period: string, benchmark: string) {
  return useQuery({
    queryKey: ["hub", "dashboard-performance", period, benchmark],
    queryFn: () =>
      api.get<DashboardPerformanceResponse>(
        `/api/finance/dashboard/performance-indexed?period=${period}&benchmark=${benchmark}`,
      ),
    staleTime: 60_000,
  })
}

// --- Single Stock tab (Chunk 4) -----------------------------------------------

export interface StockUniverseEntry {
  ticker: string
  name: string
}

export interface StockUniverseResponse {
  held: StockUniverseEntry[]
  watchlist: StockUniverseEntry[]
}

/** Selector source: held tickers first, then watchlist tickers not held. */
export function useStockUniverse() {
  return useQuery({
    queryKey: ["hub", "stock-universe"],
    queryFn: () => api.get<StockUniverseResponse>("/api/finance/stock-universe"),
    staleTime: 60_000,
  })
}

/** Every field is null when yfinance has nothing for it — render "—". */
export interface StockFundamentals {
  ticker: string
  name: string | null
  sector: string | null
  industry: string | null
  exchange: string | null
  currency: string | null
  quote_type: string | null
  price: number | null
  day_change_pct: number | null
  as_of: string | null
  market_cap: number | null
  pe_forward: number | null
  pe_trailing: number | null
  revenue_growth: number | null
  ebit_margin: number | null
  dividend_yield: number | null
  week52_low: number | null
  week52_high: number | null
  week52_position: number | null
  beta: number | null
  beta_benchmark: string
  fcf_yield: number | null
}

export interface StockPosition {
  ticker: string
  name: string
  quantity: number
  avg_cost: number
  cost_basis: number
  current_value: number | null
  pnl: number | null
  pnl_pct: number | null
  weight: number | null
  days_held: number | null
  first_bought: string | null
  fx_stale: boolean | null
}

export interface StockSeries {
  period: string
  points: { date: string; close: number }[]
  change_pct: number | null
}

export interface StockDetailResponse {
  ticker: string
  fundamentals: StockFundamentals
  /** null when the ticker isn't currently held. */
  position: StockPosition | null
  series: StockSeries
}

/** Fundamentals + position + price series for one ticker. The previous result is
 *  kept on screen while a new period/benchmark loads, so the pills don't blank the page. */
export function useStockDetail(ticker: string | null, period: string, benchmark: string) {
  return useQuery({
    queryKey: ["hub", "stock-detail", ticker, period, benchmark],
    queryFn: () =>
      api.get<StockDetailResponse>(
        `/api/finance/stock-detail/${encodeURIComponent(ticker!)}?period=${period}&benchmark=${benchmark}`,
      ),
    enabled: !!ticker,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  })
}

export interface PeerRow {
  ticker: string
  name: string | null
  sector: string | null
  market_cap: number | null
  pe_forward: number | null
  ytd_return: number | null
  return_1y: number | null
  is_subject: boolean
  /** false = nearest same-sector name outside the +/-50% market-cap band; null for custom peers. */
  in_band: boolean | null
}

export interface PeersResponse {
  ticker: string
  /** "auto" = derived (same sector, market cap +/-50%); "override" = a saved custom list. */
  source: "auto" | "override"
  peers: PeerRow[]
}

export function usePeers(ticker: string | null) {
  return useQuery({
    queryKey: ["hub", "peers", ticker],
    queryFn: () => api.get<PeersResponse>(`/api/finance/peers/${encodeURIComponent(ticker!)}`),
    enabled: !!ticker,
    staleTime: 60_000,
  })
}

/** Save a custom peer list for ``ticker`` (an empty list clears it -> back to auto).
 *  Mirrors usePatchPositionBucket: one PATCH, and the response is the fresh table. */
export function usePatchPeers(ticker: string | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (peers: string[]) =>
      api.patch<PeersResponse>(`/api/finance/peers/${encodeURIComponent(ticker!)}`, { peers }),
    onSuccess: (data) => {
      qc.setQueryData(["hub", "peers", ticker], data)
    },
  })
}

// --- Benchmarks tab (Chunk 5) -------------------------------------------------

export type BenchmarkKey4 = "MSCI_WORLD" | "SPY" | "DAX" | "STOXX_600"

export interface BenchmarkMeta {
  key: BenchmarkKey4
  name: string
  ticker: string
  /** false = no cached prices; the row renders "—" and the series is skipped. */
  available: boolean
}

export interface BenchmarkMetrics {
  return: number | null
  vol: number | null
  sharpe: number | null
  /** 1.0 for MSCI World itself (shown as "—"). */
  correlation_to_msci: number | null
}

export interface BenchmarkComparisonResponse {
  period: string
  start: string | null
  end: string | null
  risk_free_rate: number
  benchmarks: BenchmarkMeta[]
  metrics: Record<BenchmarkKey4, BenchmarkMetrics>
  correlation: { keys: BenchmarkKey4[]; labels: string[]; matrix: (number | null)[][] }
  /** One row per date: {date, MSCI_WORLD: 100, SPY: ..., ...}; unavailable benchmarks omitted. */
  series: ({ date: string } & Partial<Record<BenchmarkKey4, number>>)[]
}

/** Metrics + correlation matrix + indexed series for all four benchmarks, one call.
 *  The previous period stays on screen while the next one loads (no blank flash). */
export function useBenchmarkComparison(period: string) {
  return useQuery({
    queryKey: ["hub", "benchmarks", period],
    queryFn: () => api.get<BenchmarkComparisonResponse>(`/api/finance/benchmarks/compare?period=${period}`),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
  })
}

// --- Deployment plans / 50-30-20 tranche tracker (Chunk 6) --------------------

export type DeploymentStatus = "in_progress" | "complete" | "cancelled"
export type DeploymentBucket = "etf_foundation" | "single_stocks" | "crypto" | "wild_cards"

export interface DeploymentTranche {
  pct: number
  target_date: string
  executed: boolean
  amount_eur: number | null
  trade_id: string | null
  executed_date: string | null
}

export interface DeploymentNextTranche {
  index: number
  pct: number
  target_date: string
  /** Negative = overdue. */
  days_until: number
}

export interface DeploymentProgress {
  /** Sum of the executed tranches' percentages. */
  deployed_pct: number
  deployed_eur: number
  planned_eur: number
  executed_count: number
  tranche_count: number
  next_tranche: DeploymentNextTranche | null
}

export interface DeploymentPlan {
  id: string
  name: string
  total_eur: number
  target_bucket: DeploymentBucket | null
  target_ticker: string | null
  schedule: DeploymentTranche[]
  created_at: string
  status: DeploymentStatus
  progress: DeploymentProgress
}

export interface DeploymentPlansResponse {
  plans: DeploymentPlan[]
  summary: {
    active_count: number
    total_count: number
    next_due: (DeploymentNextTranche & { plan_id: string; plan_name: string }) | null
  }
}

export function useDeploymentPlans(status?: DeploymentStatus) {
  return useQuery({
    queryKey: ["hub", "deployment-plans", status ?? "all"],
    queryFn: () =>
      api.get<DeploymentPlansResponse>(`/api/finance/deployment-plans${status ? `?status=${status}` : ""}`),
    staleTime: 30_000,
  })
}

export interface NewDeploymentPlan {
  name: string
  total_eur: number
  target_bucket?: DeploymentBucket | null
  target_ticker?: string | null
  /** Omit for the default 50/30/20 at now / +4w / +9w. */
  schedule?: { pct: number; target_date: string }[]
}

// Every mutation invalidates all of ["hub"] so the Portfolio tab, and anything
// else reading plan state, stays in sync (the brief's "broad invalidation").
function useInvalidateHub() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: ["hub"] })
}

export function useCreateDeploymentPlan() {
  const invalidate = useInvalidateHub()
  return useMutation({
    mutationFn: (plan: NewDeploymentPlan) => api.post<DeploymentPlan>("/api/finance/deployment-plans", plan),
    onSuccess: invalidate,
  })
}

export function useUpdateDeploymentPlan() {
  const invalidate = useInvalidateHub()
  return useMutation({
    mutationFn: ({ id, ...patch }: {
      id: string
      name?: string
      total_eur?: number
      target_bucket?: DeploymentBucket | null
      target_ticker?: string | null
      status?: DeploymentStatus
      tranche_dates?: Record<number, string>
    }) => api.patch<DeploymentPlan>(`/api/finance/deployment-plans/${encodeURIComponent(id)}`, patch),
    onSuccess: invalidate,
  })
}

export function useDeleteDeploymentPlan() {
  const invalidate = useInvalidateHub()
  return useMutation({
    mutationFn: (id: string) => api.delete<{ ok: boolean }>(`/api/finance/deployment-plans/${encodeURIComponent(id)}`),
    onSuccess: invalidate,
  })
}

export function useMarkTrancheExecuted() {
  const invalidate = useInvalidateHub()
  return useMutation({
    mutationFn: ({ id, index, ...body }: { id: string; index: number; amount_eur: number; executed_date?: string; trade_id?: string }) =>
      api.post<DeploymentPlan>(
        `/api/finance/deployment-plans/${encodeURIComponent(id)}/tranches/${index}/execute`,
        body,
      ),
    onSuccess: invalidate,
  })
}
