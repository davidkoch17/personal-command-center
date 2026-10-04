import { useSearchParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { InfoBarrierBanner } from "@/components/ui/info-barrier-banner"
import { PortfolioTab } from "@/components/portfolio/portfolio-tab"
import { HoldingsTab } from "@/components/portfolio/holdings-tab"
import { WatchlistTab } from "@/components/portfolio/watchlist-tab"
import { CapturesTab } from "@/components/portfolio/captures-tab"
import { ResearchTab } from "@/components/portfolio/research-tab"
import { SingleStockTab } from "@/components/portfolio/single-stock-tab"
import { BenchmarksTab } from "@/components/portfolio/benchmarks-tab"

// "portfolio" (Chunk 2) is first — David's main portfolio dashboard, and the
// default tab (Chunk 9.8: Overview was removed — its wealth-focused purpose
// is now the dedicated Net Worth pillar, see sidebar.tsx). The rest keep
// their existing order. "stock" (Chunk 4, Single Stock) is appended last —
// slug follows the existing one-word convention; the selected ticker rides
// along as ?ticker=.
const TABS = ["portfolio", "holdings", "watchlist", "captures", "research", "stock", "benchmarks"] as const
type Tab = (typeof TABS)[number]

/**
 * Portfolio Hub (Pillar 1, v3 spec § d) — a single page with sub-nav tabs.
 * Refactors the v2 Portfolio + Watchlist + Money pages onto their existing
 * backends. Default tab = Portfolio. No Briefing tab (moved to Projects pillar).
 */
export function Portfolio() {
  const [params, setParams] = useSearchParams()
  const raw = params.get("tab")
  const tab: Tab = (TABS as readonly string[]).includes(raw ?? "") ? (raw as Tab) : "portfolio"

  function setTab(t: string) {
    setParams((p) => {
      p.set("tab", t)
      return p
    })
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">portfolio hub</h1>
        <Button asChild variant="secondary" size="sm">
          <a href="/workspace/portfolio" target="_blank" rel="noopener noreferrer">
            open workspace ↗
          </a>
        </Button>
      </div>

      <InfoBarrierBanner message="restricted-sector names may be involved" />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="portfolio">portfolio</TabsTrigger>
          <TabsTrigger value="holdings">holdings</TabsTrigger>
          <TabsTrigger value="watchlist">watchlist</TabsTrigger>
          <TabsTrigger value="captures">captures</TabsTrigger>
          <TabsTrigger value="research">research</TabsTrigger>
          <TabsTrigger value="stock">single stock</TabsTrigger>
          <TabsTrigger value="benchmarks">benchmarks</TabsTrigger>
        </TabsList>

        <TabsContent value="portfolio">{tab === "portfolio" && <PortfolioTab />}</TabsContent>
        <TabsContent value="holdings">{tab === "holdings" && <HoldingsTab />}</TabsContent>
        <TabsContent value="watchlist">{tab === "watchlist" && <WatchlistTab />}</TabsContent>
        <TabsContent value="captures">{tab === "captures" && <CapturesTab />}</TabsContent>
        <TabsContent value="research">{tab === "research" && <ResearchTab />}</TabsContent>
        <TabsContent value="stock">{tab === "stock" && <SingleStockTab />}</TabsContent>
        <TabsContent value="benchmarks">{tab === "benchmarks" && <BenchmarksTab />}</TabsContent>
      </Tabs>
    </div>
  )
}
