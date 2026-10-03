import { useMutation } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { useBenchmark } from "@/hooks/useBenchmark"
import { useRiskFreeRate } from "@/hooks/useRiskFreeRate"
import type { FrontierPoint, OptPortfolio } from "@/hooks/useFinance"

export interface BoundConstraint {
  min: number | null
  max: number | null
}

export interface ConcentrationConstraint {
  max_single: number | null
  max_top5: number | null
  hhi_cap: number | null
}

/** Mirrors backend/api/finance/optimization.py's ConstraintSetRequest — a
 *  section is ``null`` when its modal toggle is off, and is then never sent
 *  to the solver at all (D8's "isolate which constraint drives the delta"). */
export interface ConstraintSet {
  bucket_caps: Record<string, BoundConstraint> | null
  position_bounds: Record<string, BoundConstraint> | null
  concentration: ConcentrationConstraint | null
  currency_caps: Record<string, number> | null
  vol_budget: { max_vol: number } | null
}

export interface ConstrainedFrontierResult {
  points: FrontierPoint[]
  tangency: OptPortfolio | null
  mvp: OptPortfolio | null
  feasible: boolean
  binding_constraint: string | null
  reason: string | null
}

export interface ConstrainedFrontierResponse {
  tickers: string[]
  constrained: ConstrainedFrontierResult
}

/** POST /optimization/frontier-with-constraints — the D8 "Preview" action.
 *  Reads the shared benchmark itself so the overlay is always built from the
 *  same CAPM expected returns as the base frontier it is drawn over. */
export function useOptimizationConstrained() {
  const [benchmark] = useBenchmark()
  const [rfr] = useRiskFreeRate()
  return useMutation({
    mutationFn: (req: ConstraintSet & { tickers?: string[]; n_points?: number }) =>
      api.post<ConstrainedFrontierResponse>("/api/finance/optimization/frontier-with-constraints", {
        ...req,
        benchmark,
        rfr,
      }),
  })
}
