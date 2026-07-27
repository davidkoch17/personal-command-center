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

export function useCashflowReserve(month: string | null) {
  return useQuery({
    queryKey: ["cashflow", "reserve", month],
    queryFn: () => api.get<CashflowReserveResponse>(`/api/cashflow/reserve/${month}`),
    enabled: !!month,
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
