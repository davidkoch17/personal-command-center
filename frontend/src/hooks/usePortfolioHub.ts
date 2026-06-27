/**
 * Phase D — Portfolio Hub data hooks.
 *
 * Wraps the new backend endpoints for the five Portfolio-Hub tabs:
 * - Overview   : net-worth daily series + this-month decomposition
 * - Holdings   : per-position period P&L + realized trade log
 * - Watchlist  : Connected News (captures per ticker) + sector radar + plan card
 * - Captures   : captures list / detail / routing
 * - Research   : reports library + run launcher + hypotheses
 *
 * Decision-alerts (Overview strip) reuse `useDecisionSummary` from useFinance;
 * the Decision Log (Research tab) reuses `useDecisions` / `useLogDecision`.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
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

// --- Holdings ---------------------------------------------------------------

export interface PnlPosition {
  ticker: string
  name: string
  type: string | null
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
