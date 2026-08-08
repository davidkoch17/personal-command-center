import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

// --- Types (mirror backend/api/cashflow.py) ---------------------------------

export interface CashflowCategoriesResponse {
  expense_categories: string[]
  income_categories: string[]
}

export interface CashflowExpenseCategory {
  category: string
  amount: number
}

export interface CashflowGoalProgress {
  month: string
  goal: number | null
  actual_savings: number
  percent_of_goal: number | null
  on_track: boolean | null
}

export interface CashflowSummaryResponse {
  month: string
  income_by_category: Record<string, number>
  income_total: number
  expenses_by_category: CashflowExpenseCategory[]
  expenses_total: number
  net: number
  savings_rate: number | null
  goal: CashflowGoalProgress
}

export interface CashflowTrendPoint {
  month: string
  income: number
  expenses: number
  savings: number
}

export interface CashflowTransaction {
  date: string
  direction: "income" | "expense"
  description: string
  amount: number
  category: string
  account: string
  notes: string
}

export interface CashflowReserveStatus {
  month: string
  reserve_balance: number | null
  target: number
  percent_filled: number | null
  remaining_to_target: number | null
}

export interface CashflowContributionEstimate {
  value: number | null
  reliable: boolean
  flags: string[]
  depot_value_change: number | null
  market_pnl: number | null
}

export interface CashflowActualContribution {
  month: string
  value: number | null
  source: "explicit_deposits" | "manual_override" | "estimated" | null
  reliable: boolean
  flags: string[]
  estimate: CashflowContributionEstimate
}

export interface CashflowNeedsReviewEntry {
  id: string
  date: string
  direction: "income" | "expense"
  amount: number
  category: string
  account: string | null
  description: string
  source_file: string | null
  notes: string | null
  needs_review: boolean
  question: string | null
  question_type: "category" | "freetext"
}

export interface CashflowResolveRequest {
  date?: string
  direction?: "income" | "expense"
  amount?: number
  category?: string
  account?: string | null
  description?: string
  notes?: string | null
}

export interface CashflowReserveResponse {
  month: string
  investable_income: number
  investable_surplus: number
  savings_rate: number | null
  reserve: CashflowReserveStatus
  split_recommendation: { to_reserve: number; to_invest: number }
  actual_contribution: CashflowActualContribution
  contribution_vs_recommended: number | null
}

export interface CashflowMetricWithTrend {
  total: number
  avg_3mo: number | null
  delta_percent: number | null
}

export interface CashflowTopCategory {
  category: string
  amount: number
  percent_of_total: number
}

export interface CashflowBiggestMover {
  category: string
  delta_percent: number
}

export interface CashflowAccount {
  name: string
  balance: number
  is_reserve: boolean
}

export interface CashflowAccountsResponse {
  accounts: CashflowAccount[]
  total_cash: number
}

export interface CashflowOverviewResponse {
  month: string
  income: CashflowMetricWithTrend
  expenses: CashflowMetricWithTrend
  net: CashflowMetricWithTrend
  savings_rate: number | null
  runway_months: number | null
  reserve: CashflowReserveStatus
  split_recommendation: { to_reserve: number; to_invest: number }
  investable_surplus: number
  top_categories: CashflowTopCategory[]
  biggest_mover: CashflowBiggestMover | null
}

export interface CashflowFixedVsVariable {
  month: string
  fixed: number
  variable: number
  fixed_share: number | null
}

export interface CashflowRecurringItem {
  merchant: string
  amount: number
  cadence: "weekly" | "monthly" | "quarterly" | "yearly"
  category: string
  last_seen: string
  occurrences: number
  price_creep: boolean
  price_creep_delta: number | null
  monthly_equivalent: number
}

export interface CashflowRecurringResponse {
  items: CashflowRecurringItem[]
  committed_monthly_total: number
}

export interface CashflowMerchant {
  merchant: string
  amount: number
}

export interface CashflowSpendingCategory {
  category: string
  amount: number
  type: "fixed" | "variable"
  merchants: CashflowMerchant[]
}

export interface CashflowSpendingMover {
  category: string
  amount: number
  avg_3mo: number
  delta_percent: number
}

export interface CashflowSpendingResponse {
  month: string
  fixed_vs_variable: CashflowFixedVsVariable
  recurring: CashflowRecurringResponse
  categories: CashflowSpendingCategory[]
  biggest_movers: CashflowSpendingMover[]
}

export interface CashflowRunway {
  as_of: string
  total_cash: number
  reserve_balance: number
  monthly_burn: number | null
  months_total: number | null
  cash_lasts_until: string | null
  months_before_reserve_drawdown: number | null
  reserve_drawdown_date: string | null
}

export interface CashflowRunwayScenario {
  monthly_burn: number
  months_total: number | null
  cash_lasts_until: string | null
}

export interface CashflowRunwayScenariosResponse {
  base: CashflowRunway
  cut_variable_25: CashflowRunwayScenario | null
  cut_variable_50: CashflowRunwayScenario | null
}

export interface CashflowForecastMonth {
  month: string
  projected_income: number
  projected_bills: number
  projected_surplus: number
  to_reserve: number
  to_invest: number
  projected_reserve_balance: number
}

export interface CashflowForecastResponse {
  base_month: string
  recurring_income: number
  committed_bills: number
  reserve_target: number
  months: CashflowForecastMonth[]
  reserve_fill_month: string | null
  invest_start_month: string | null
}

export interface CashflowTrendsPoint {
  month: string
  savings_rate: number | null
  income_stability: number | null
}

export type CashflowAlertSeverity = "high" | "medium" | "low"
export type CashflowAlertTab = "overview" | "spending" | "reserve"

export interface CashflowAlert {
  id: string
  type: string
  severity: CashflowAlertSeverity
  message: string
  tab: CashflowAlertTab
}

export interface CashflowAlertsResponse {
  month: string
  alerts: CashflowAlert[]
}

// --- Queries -----------------------------------------------------------------

export function useCashflowCategories() {
  return useQuery({
    queryKey: ["cashflow", "categories"],
    queryFn: () => api.get<CashflowCategoriesResponse>("/api/cashflow/categories"),
    staleTime: 5 * 60_000,
  })
}

export function useCashflowMonths() {
  return useQuery({
    queryKey: ["cashflow", "months"],
    queryFn: () => api.get<{ months: string[] }>("/api/cashflow/months"),
    staleTime: 30_000,
  })
}

export function useCashflowSummary(month: string | null) {
  return useQuery({
    queryKey: ["cashflow", "summary", month],
    queryFn: () => api.get<CashflowSummaryResponse>(`/api/cashflow/summary/${month}`),
    enabled: !!month,
    staleTime: 30_000,
  })
}

export function useCashflowTrend(months = 12) {
  return useQuery({
    queryKey: ["cashflow", "trend", months],
    queryFn: () => api.get<{ months: number; trend: CashflowTrendPoint[] }>(`/api/cashflow/trend?months=${months}`),
  })
}

export function useCashflowCategoryTrend(months = 12) {
  return useQuery({
    queryKey: ["cashflow", "category-trend", months],
    queryFn: () =>
      api.get<{ months: number; categories: Record<string, string | number | null>[] }>(
        `/api/cashflow/category-trend?months=${months}`,
      ),
  })
}

export function useCashflowTransactions(month: string | null) {
  return useQuery({
    queryKey: ["cashflow", "transactions", month],
    queryFn: () => api.get<{ month: string; transactions: CashflowTransaction[] }>(`/api/cashflow/transactions/${month}`),
    enabled: !!month,
    staleTime: 30_000,
  })
}

export function useCashflowOverview(month: string | null) {
  return useQuery({
    queryKey: ["cashflow", "overview", month],
    queryFn: () => api.get<CashflowOverviewResponse>(`/api/cashflow/overview/${month}`),
    enabled: !!month,
    staleTime: 30_000,
  })
}

export function useCashflowSpending(month: string | null) {
  return useQuery({
    queryKey: ["cashflow", "spending", month],
    queryFn: () => api.get<CashflowSpendingResponse>(`/api/cashflow/spending/${month}`),
    enabled: !!month,
    staleTime: 30_000,
  })
}

export function useCashflowReserve(month: string | null) {
  return useQuery({
    queryKey: ["cashflow", "reserve", month],
    queryFn: () => api.get<CashflowReserveResponse>(`/api/cashflow/reserve/${month}`),
    enabled: !!month,
    staleTime: 30_000,
  })
}

export function useCashflowAccounts() {
  return useQuery({
    queryKey: ["cashflow", "accounts"],
    queryFn: () => api.get<CashflowAccountsResponse>("/api/cashflow/accounts"),
    staleTime: 30_000,
  })
}

export function useCashflowGoal() {
  return useQuery({
    queryKey: ["cashflow", "goal"],
    queryFn: () => api.get<{ monthly_savings_goal: number | null }>("/api/cashflow/goal"),
  })
}

export function useCashflowBudget() {
  return useQuery({
    queryKey: ["cashflow", "budget"],
    queryFn: () => api.get<{ budget: Record<string, number> }>("/api/cashflow/budget"),
  })
}

export function useCashflowRunway() {
  return useQuery({
    queryKey: ["cashflow", "runway"],
    queryFn: () => api.get<CashflowRunway>("/api/cashflow/runway"),
    staleTime: 30_000,
  })
}

export function useCashflowRunwayScenarios() {
  return useQuery({
    queryKey: ["cashflow", "runway-scenarios"],
    queryFn: () => api.get<CashflowRunwayScenariosResponse>("/api/cashflow/runway/scenarios"),
    staleTime: 30_000,
  })
}

export function useCashflowForecast(months = 6) {
  return useQuery({
    queryKey: ["cashflow", "forecast", months],
    queryFn: () => api.get<CashflowForecastResponse>(`/api/cashflow/forecast?months=${months}`),
    staleTime: 30_000,
  })
}

export function useCashflowTrends(months = 12) {
  return useQuery({
    queryKey: ["cashflow", "trends", months],
    queryFn: () => api.get<{ months: number; trends: CashflowTrendsPoint[] }>(`/api/cashflow/trends?months=${months}`),
    staleTime: 30_000,
  })
}

export function useCashflowExpectedIncome() {
  return useQuery({
    queryKey: ["cashflow", "expected-income"],
    queryFn: () => api.get<{ monthly_amount: number | null }>("/api/cashflow/config/expected-income"),
    staleTime: 30_000,
  })
}

export function useCashflowAlerts(month: string | null) {
  return useQuery({
    queryKey: ["cashflow", "alerts", month],
    queryFn: () => api.get<CashflowAlertsResponse>(`/api/cashflow/alerts/${month}`),
    enabled: !!month,
    staleTime: 30_000,
  })
}

export function useCashflowNeedsReview() {
  return useQuery({
    queryKey: ["cashflow", "needs-review"],
    queryFn: () =>
      api.get<{ entries: CashflowNeedsReviewEntry[]; count: number }>("/api/cashflow/needs-review"),
    staleTime: 30_000,
  })
}

// --- Mutations -----------------------------------------------------------------

export function useSetReserveBalance() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ month, value }: { month: string; value: number }) =>
      api.post<{ ok: boolean; month: string; value: number }>(`/api/cashflow/reserve/${month}/balance`, { value }),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["cashflow", "reserve", variables.month] })
    },
  })
}

export function useSetCashflowReserveTarget() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (value: number) =>
      api.post<{ ok: boolean; target: number }>("/api/cashflow/config/reserve-target", { value }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cashflow", "overview"] })
      qc.invalidateQueries({ queryKey: ["cashflow", "reserve"] })
    },
  })
}

export function useSetCashflowExpectedIncome() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (value: number | null) =>
      api.post<{ ok: boolean; monthly_amount: number | null }>("/api/cashflow/config/expected-income", { value }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cashflow", "expected-income"] })
      qc.invalidateQueries({ queryKey: ["cashflow", "forecast"] })
    },
  })
}

export function useSetCashflowGoal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (value: number | null) =>
      api.post<{ ok: boolean; monthly_savings_goal: number | null }>("/api/cashflow/goal", { value }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cashflow", "goal"] })
      qc.invalidateQueries({ queryKey: ["cashflow", "summary"] })
    },
  })
}

export function useSetCashflowBudget() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ category, value }: { category: string; value: number | null }) =>
      api.post<{ ok: boolean; budget: Record<string, number> }>("/api/cashflow/budget", { category, value }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cashflow", "budget"] })
    },
  })
}

// Account balances feed runway (total cash + reserve balance) and the
// low-runway/reserve-milestone alerts on the backend, so both must be
// invalidated alongside "accounts" or the Runway panel and alerts strip
// keep showing pre-edit figures until an unrelated refetch happens.
export function useSetCashflowAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (account: CashflowAccount) =>
      api.post<{ ok: boolean; accounts: CashflowAccount[] }>("/api/cashflow/accounts", account),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cashflow", "accounts"] })
      qc.invalidateQueries({ queryKey: ["cashflow", "runway"] })
      qc.invalidateQueries({ queryKey: ["cashflow", "runway-scenarios"] })
      qc.invalidateQueries({ queryKey: ["cashflow", "alerts"] })
    },
  })
}

export function useDeleteCashflowAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) =>
      api.delete<{ ok: boolean; accounts: CashflowAccount[] }>(`/api/cashflow/accounts/${encodeURIComponent(name)}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cashflow", "accounts"] })
      qc.invalidateQueries({ queryKey: ["cashflow", "runway"] })
      qc.invalidateQueries({ queryKey: ["cashflow", "runway-scenarios"] })
      qc.invalidateQueries({ queryKey: ["cashflow", "alerts"] })
    },
  })
}

export function useResolveCashflowEntry() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...fields }: CashflowResolveRequest & { id: string }) =>
      api.post<{ ok: boolean; entry: CashflowNeedsReviewEntry }>(
        `/api/cashflow/needs-review/${encodeURIComponent(id)}/resolve`,
        fields,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cashflow"] })
    },
  })
}
