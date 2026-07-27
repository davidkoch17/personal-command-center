import { useSearchParams } from "react-router-dom"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Tag } from "@/components/ui/tag"
import { OverviewTab } from "@/components/cashflow/overview-tab"
import { CategoriesTab } from "@/components/cashflow/categories-tab"
import { TransactionsTab } from "@/components/cashflow/transactions-tab"
import { ReserveTab } from "@/components/cashflow/reserve-tab"
import { BudgetTab } from "@/components/cashflow/budget-tab"
import { useCashflowNeedsReview } from "@/hooks/useCashflow"

const TABS = ["overview", "categories", "transactions", "reserve", "budget"] as const
type Tab = (typeof TABS)[number]

/**
 * Cash Flow pillar — income/expense analysis, sourced from the ledger David
 * hands Claude directly (statements, receipts, screenshots), not Excel.
 */
export function CashFlow() {
  const [params, setParams] = useSearchParams()
  const raw = params.get("tab")
  const tab: Tab = (TABS as readonly string[]).includes(raw ?? "") ? (raw as Tab) : "overview"
  const needsReviewCount = useCashflowNeedsReview().data?.count ?? 0

  function setTab(t: string) {
    setParams((p) => {
      p.set("tab", t)
      return p
    })
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">cash flow</h1>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="overview">
            <span className="flex items-center gap-1.5">
              overview
              {needsReviewCount > 0 && (
                <Tag variant="warning" className="px-1.5 py-0">
                  {needsReviewCount}
                </Tag>
              )}
            </span>
          </TabsTrigger>
          <TabsTrigger value="categories">categories</TabsTrigger>
          <TabsTrigger value="transactions">transactions</TabsTrigger>
          <TabsTrigger value="reserve">reserve & allocation</TabsTrigger>
          <TabsTrigger value="budget">budget</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">{tab === "overview" && <OverviewTab />}</TabsContent>
        <TabsContent value="categories">{tab === "categories" && <CategoriesTab />}</TabsContent>
        <TabsContent value="transactions">{tab === "transactions" && <TransactionsTab />}</TabsContent>
        <TabsContent value="reserve">{tab === "reserve" && <ReserveTab />}</TabsContent>
        <TabsContent value="budget">{tab === "budget" && <BudgetTab />}</TabsContent>
      </Tabs>
    </div>
  )
}
