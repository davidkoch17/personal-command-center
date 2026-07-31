import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { CategoryDonut, CategoryTrendLine } from "@/components/charts/finance-charts"
import { useCashflowCategoryTrend } from "@/hooks/useCashflow"
import { categoryNames, lastCategoryBreakdown } from "@/lib/money"

export function CategoriesTab() {
  const trend = useCashflowCategoryTrend(12)
  const rows = trend.data?.categories ?? []
  const breakdown = lastCategoryBreakdown(rows)

  if (trend.isLoading) return <Skeleton className="h-96" />

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="this month's expense mix" statusDotColor="accent">
        {breakdown.length === 0 ? (
          <EmptyState message="no expense data for the latest month yet." />
        ) : (
          <CategoryDonut data={breakdown} height={280} />
        )}
      </Panel>
      <Panel title="category monthly trend" meta="last 12 months" statusDotColor="accent">
        {rows.length === 0 ? (
          <EmptyState message="no data yet." />
        ) : (
          <CategoryTrendLine data={rows} categories={categoryNames(rows)} />
        )}
      </Panel>
    </div>
  )
}
