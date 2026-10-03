import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { Toggle } from "@/components/ui/toggle"
import { FactorLoadingsComparisonChart, RollingFactorBetasChart } from "@/components/charts/finance-analytics-charts"
import { useFactorLoadingsComparison, useRollingFactorBetas } from "@/hooks/useFinance"
import { useBenchmark } from "@/hooks/useBenchmark"

const MODEL_OPTIONS = [
  { value: "ff3" as const, label: "ff3" },
  { value: "ff5" as const, label: "ff5" },
]

/**
 * Rolling factor betas (Chunk 8): the portfolio's β to each Fama-French factor over a trailing
 * 36-month window (the institutional norm), so a drift in exposure is visible — the static
 * regression above is one number for the whole history.
 */
export function RollingFactorBetasPanel({ region }: { region: string }) {
  const [model, setModel] = useState<"ff3" | "ff5">("ff3")
  const { data, isLoading } = useRollingFactorBetas(region, model, 36)

  return (
    <Panel
      title="rolling factor betas"
      meta={data?.available ? `${data.window_months}-month window · ${region}` : `${region}`}
      statusDotColor="accent"
    >
      <div className="mb-3 flex items-center gap-2">
        <span className="label">model</span>
        <Toggle value={model} options={MODEL_OPTIONS} onChange={setModel} />
      </div>
      {isLoading ? (
        <Skeleton className="h-64" />
      ) : !data?.available || !data.dates || !data.series ? (
        <EmptyState message={data?.reason ?? "not enough history for a rolling regression"} />
      ) : (
        <>
          <RollingFactorBetasChart dates={data.dates} series={data.series} />
          <p className="mt-2 text-xs text-text-label">
            each point regresses the trailing {data.window_months} months of excess returns on the factors; the portfolio uses
            today's weights over its full price history.
          </p>
        </>
      )}
    </Panel>
  )
}

/**
 * Portfolio vs the selected comparison benchmark's factor loadings (Chunk 8) — the same
 * regression run on both, over the same months, so a gap is a real difference in exposure.
 * Follows the Risk tab's Comparison benchmark (useBenchmark).
 */
export function FactorLoadingsComparisonPanel({ region }: { region: string }) {
  const [benchmark] = useBenchmark()
  const [model, setModel] = useState<"ff3" | "ff5">("ff3")
  const { data, isLoading } = useFactorLoadingsComparison(region, model, benchmark)

  return (
    <Panel
      title="factor loadings vs benchmark"
      meta={data?.available ? `${data.benchmark_name} · ${data.n_observations} months · ${region}` : undefined}
      statusDotColor="accent"
    >
      <div className="mb-3 flex items-center gap-2">
        <span className="label">model</span>
        <Toggle value={model} options={MODEL_OPTIONS} onChange={setModel} />
      </div>
      {isLoading ? (
        <Skeleton className="h-56" />
      ) : !data?.available || !data.factors ? (
        <EmptyState message={data?.reason ?? "no comparison available"} />
      ) : (
        <>
          <FactorLoadingsComparisonChart data={data.factors} benchmarkName={data.benchmark_name} />
          <p className="mt-2 text-xs text-text-label">
            portfolio (solid) vs {data.benchmark_name} (hatched), both regressed on the same {data.n_observations} months.
            switch the comparison benchmark on the Risk tab.
          </p>
        </>
      )}
    </Panel>
  )
}
