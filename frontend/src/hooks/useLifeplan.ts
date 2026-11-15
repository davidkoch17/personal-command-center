import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

// --- Types (mirror modules/lifeplan/inputs.py + model.py) --------------------

export interface CareerStage {
  name: string
  age: number
  fix: number
  bonus: number
}

export interface PriceRange {
  low: number
  high: number
  price: number
}

export interface CarPrice extends PriceRange {
  fees_pct: number
}

export type MilestoneKey = "main_car" | "fun_car" | "house_munich" | "sports_car" | "house_cape"

export interface LifePlanInputs {
  start: {
    birth_year: number
    start_year: number
    start_wealth: number
    wealth_source: "manual" | "dashboard"
  }
  career: {
    path: string
    paths: Record<string, CareerStage[]>
    work_until_age: number
    bonus_factor: number
    md_age: number | null
  }
  spending: { bands: { age: number; pct: number }[] }
  family: {
    marriage_age: number
    partner_gross: number
    child1_age: number
    child2_age: number
  }
  milestones: Record<MilestoneKey, number>
  assumptions: Record<string, number>
  one_off: {
    house_munich: PriceRange
    main_car: CarPrice
    sports_car: CarPrice
    fun_car: CarPrice
  }
  running: Record<string, number>
}

export interface YearRow {
  year: number
  age: number
  salary: number
  social: number
  partner_gross: number
  partner_social: number
  taxable: number
  splitting: number
  income_tax: number
  soli_church: number
  employer_pkv: number
  net_income: number
  spend_pct: number
  lifestyle: number
  rent: number
  kids: number
  insurance: number
  homes_cars: number
  buffer: number
  loan_payment: number
  spending: number
  savings: number
  purchases: number
  new_loan: number
  debt: number
  liquid: number
  real_assets: number
  net_worth: number
  goal_reached: boolean
  warning: string
  purchased: MilestoneKey[]
}

export interface MilestoneRow {
  idx: number
  key: MilestoneKey | null
  label: string
  purchase_price: number
  loan: number
  equity: number
  fees_lost: number
  in_asset: number
  reserve: number
  liquid_needed: number
  living: number
  car_depreciation: number
  loan_payment: number
  amortization: number
  spending: number
  net_income_needed: number
  gross_income_needed: number
  purchase_age: number | null
  purchase_year: number | null
  financeable: boolean | null
}

export interface OneOffRow {
  key: string
  label: string
  price: number
  fees_pct: number
  fees: number
  total: number
}

export interface LifePlanResult {
  summary: {
    target: number
    goal_age: number | null
    goal_year: number | null
    net_worth_at: Record<string, number | null>
    min_liquid: number
    warnings: number
  }
  years: YearRow[]
  milestones: MilestoneRow[]
  one_off: OneOffRow[]
  lifestyle_variable_monthly: number
  one_off_total: number
  running_total_monthly: number
  career: CareerStage[]
}

export interface LiveWealth {
  total: number
  date: string
  components?: Record<string, number>
}

export interface LifePlanBase {
  inputs: LifePlanInputs
  result: LifePlanResult
  live_wealth: LiveWealth | null
  excel_path: string
}

export interface Scenario {
  id: string
  name: string
  created: string
  updated?: string
  overrides: Record<string, unknown>
  inputs: LifePlanInputs
}

const BASE_KEY = ["lifeplan"]
const SCEN_KEY = ["lifeplan", "scenarios"]

/** Base inputs from the Excel + computed plan + live net worth. */
export function useLifePlanBase() {
  return useQuery({
    queryKey: BASE_KEY,
    queryFn: () => api.get<LifePlanBase>("/api/lifeplan"),
    refetchOnWindowFocus: false,
  })
}

export function useScenarios() {
  return useQuery({
    queryKey: SCEN_KEY,
    queryFn: () => api.get<{ scenarios: Scenario[] }>("/api/lifeplan/scenarios"),
    refetchOnWindowFocus: false,
  })
}

/** One-off compute (base + overrides → plan). */
export function computePlan(overrides: unknown) {
  return api.post<{ inputs: LifePlanInputs; result: LifePlanResult }>(
    "/api/lifeplan/compute",
    { overrides },
  )
}

export function useSaveScenario() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; inputs: LifePlanInputs; id?: string }) =>
      api.post<Scenario>("/api/lifeplan/scenarios", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: SCEN_KEY }),
  })
}

export function useDeleteScenario() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/lifeplan/scenarios/${encodeURIComponent(id)}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: SCEN_KEY }),
  })
}

export function usePromote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (inputs: LifePlanInputs) =>
      api.post<{ backup: string; changed: string[]; inputs: LifePlanInputs; result: LifePlanResult }>(
        "/api/lifeplan/promote",
        { inputs },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: BASE_KEY })
    },
  })
}

export function openExcel() {
  return api.post<{ ok: boolean; opened: string }>("/api/lifeplan/open-excel")
}
