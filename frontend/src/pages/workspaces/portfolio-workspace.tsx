import { useState } from "react"
import { Link } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { NumberDisplay } from "@/components/ui/number-display"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { HoldingsTable } from "@/components/finance/holdings-table"
import { HoldingSubview } from "@/components/finance/holding-subview"
import {
  AllocationBar,
  CategoryDonut,
  PerformanceArea,
} from "@/components/charts/finance-charts"
import { CHART_COLORS } from "@/components/charts/theme"
import {
  usePortfolioSnapshot,
  usePortfolioPerformance,
  usePortfolioAllocations,
  type HoldingRow,
} from "@/hooks/useFinance"
import { useRunSkill } from "@/hooks/useSkills"
import { toast } from "@/lib/toast-store"
import { formatCurrency } from "@/lib/utils"

function pick(row: HoldingRow, match: string): number | null {
  const key = Object.keys(row).find((k) => k.includes(match))
  const v = key ? row[key] : null
  return typeof v === "number" ? v : null
}
function pickStr(row: HoldingRow, match: string): string {
  const key = Object.keys(row).find((k) => k.includes(match))
  return key ? String(row[key] ?? "") : ""
}

const SCENARIO_EXAMPLES = [
  "if I sell my largest position → cash + tax impact",
  "if the market drops 20% → portfolio value + recovery",
  "if EUR/USD moves 10% → which positions hurt",
  "if I add 5% to a ticker → new allocation + concentration",
]

export function PortfolioWorkspace() {
  const snap = usePortfolioSnapshot()
  const perf = usePortfolioPerformance("ytd")
  const alloc = usePortfolioAllocations()
  const [selected, setSelected] = useState<HoldingRow | null>(null)

  const holdings = snap.data?.holdings ?? []

  return (
    <div className="min-h-screen bg-bg text-text p-6">
      <div className="mx-auto max-w-[1400px] space-y-5">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">portfolio workspace</h1>
          <Link to="/portfolio" className="font-mono text-xs text-text-secondary hover:text-accent">
            ← portfolio
          </Link>
        </div>

        {selected ? (
          <HoldingSubview holding={selected} onBack={() => setSelected(null)} />
        ) : (
          <Tabs defaultValue="holdings">
            <TabsList>
              <TabsTrigger value="holdings">holdings</TabsTrigger>
              <TabsTrigger value="allocations">allocations</TabsTrigger>
              <TabsTrigger value="performance">performance</TabsTrigger>
              <TabsTrigger value="attribution">attribution</TabsTrigger>
              <TabsTrigger value="risk">risk</TabsTrigger>
              <TabsTrigger value="scenarios">scenarios</TabsTrigger>
              <TabsTrigger value="tax">tax</TabsTrigger>
            </TabsList>

            {/* 1. Holdings */}
            <TabsContent value="holdings">
              <Panel title="holdings" meta={`${holdings.length} positions · click a row`} statusDotColor="accent">
                {snap.isLoading ? (
                  <Skeleton className="h-40" />
                ) : (
                  <HoldingsTable holdings={holdings} onRowClick={setSelected} />
                )}
              </Panel>
            </TabsContent>

            {/* 2. Allocations */}
            <TabsContent value="allocations">
              <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="by type" statusDotColor="accent">
                  {alloc.isLoading ? (
                    <Skeleton className="h-48" />
                  ) : (
                    <AllocationBar
                      data={(alloc.data?.by_type ?? []).map((t) => ({ type: t.type, value: t.value }))}
                    />
                  )}
                </Panel>
                <Panel title="composition" statusDotColor="accent">
                  {alloc.isLoading ? (
                    <Skeleton className="h-48" />
                  ) : (
                    <CategoryDonut
                      data={(alloc.data?.by_type ?? []).map((t) => ({ name: t.type, value: t.value }))}
                    />
                  )}
                </Panel>
                <Panel title="asset class over time" meta="tr vs crypto" statusDotColor="accent" className="lg:col-span-2">
                  {perf.isLoading ? (
                    <Skeleton className="h-64" />
                  ) : (
                    <PerformanceArea
                      data={perf.data?.by_month ?? []}
                      series={[
                        { key: "Trade Republic", color: CHART_COLORS.accent },
                        { key: "Crypto", color: CHART_COLORS.warning },
                      ]}
                    />
                  )}
                  <p className="mt-2 text-xs text-text-label">
                    sector / region / currency breakdowns need richer source columns (pending)
                  </p>
                </Panel>
              </div>
            </TabsContent>

            {/* 3. Performance */}
            <TabsContent value="performance">
              <Panel
                title="portfolio value over time"
                meta={perf.data?.change_pct != null ? `ytd ${perf.data.change_pct.toFixed(1)}%` : undefined}
                statusDotColor="accent"
              >
                {perf.isLoading ? (
                  <Skeleton className="h-64" />
                ) : (
                  <PerformanceArea
                    data={perf.data?.by_month ?? []}
                    series={[{ key: "Total", color: CHART_COLORS.accent }]}
                  />
                )}
                <p className="mt-2 text-xs text-text-label">
                  benchmark overlays (spy / msci world) + rolling sharpe pending
                </p>
              </Panel>
            </TabsContent>

            {/* 4. Attribution */}
            <TabsContent value="attribution">
              <AttributionTab holdings={holdings} loading={snap.isLoading} />
            </TabsContent>

            {/* 5. Risk */}
            <TabsContent value="risk">
              <RiskTab
                byPosition={alloc.data?.by_position ?? []}
                loading={alloc.isLoading}
              />
            </TabsContent>

            {/* 6. Scenarios */}
            <TabsContent value="scenarios">
              <ScenariosTab />
            </TabsContent>

            {/* 7. Tax */}
            <TabsContent value="tax">
              <TaxTab holdings={holdings} loading={snap.isLoading} />
            </TabsContent>
          </Tabs>
        )}
      </div>
    </div>
  )
}

// 4. Attribution — derived: contribution = market value × (%YTD / 100)
function AttributionTab({ holdings, loading }: { holdings: HoldingRow[]; loading: boolean }) {
  if (loading) return <Skeleton className="h-40" />
  const contribs = holdings
    .map((h) => ({
      name: pickStr(h, "Position"),
      contribution: (pick(h, "Market Value") ?? 0) * ((pick(h, "% YTD") ?? 0) / 100),
    }))
    .filter((c) => c.contribution !== 0)
    .sort((a, b) => b.contribution - a.contribution)

  const top = contribs.slice(0, 5)
  const bottom = contribs.slice(-5).reverse()

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Panel title="top contributors" meta="ytd, est." statusDotColor="success">
        <AttribList rows={top} />
      </Panel>
      <Panel title="top detractors" meta="ytd, est." statusDotColor="danger">
        <AttribList rows={bottom} />
      </Panel>
      <p className="md:col-span-2 text-xs text-text-label">
        estimated as market value × % ytd. currency vs price decomposition pending.
      </p>
    </div>
  )
}

function AttribList({ rows }: { rows: { name: string; contribution: number }[] }) {
  if (rows.length === 0) return <p className="text-sm text-text-label">no data</p>
  return (
    <ul className="space-y-1 text-sm">
      {rows.map((r, i) => (
        <li key={i} className="flex items-center justify-between gap-2">
          <span className="truncate text-text">{r.name}</span>
          <NumberDisplay value={r.contribution} format="currency" signed />
        </li>
      ))}
    </ul>
  )
}

// 5. Risk — concentration from position weights
function RiskTab({
  byPosition,
  loading,
}: {
  byPosition: { name: string; weight_pct: number | null }[]
  loading: boolean
}) {
  if (loading) return <Skeleton className="h-40" />
  const sorted = [...byPosition].sort((a, b) => (b.weight_pct ?? 0) - (a.weight_pct ?? 0))
  const top3 = sorted.slice(0, 3).reduce((s, p) => s + (p.weight_pct ?? 0), 0)

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Panel title="concentration" statusDotColor={top3 > 60 ? "danger" : "accent"}>
        <div className="label mb-0.5">top-3 weight</div>
        <NumberDisplay value={top3} format="percent" emphasized className="text-2xl" />
      </Panel>
      <Panel title="position weights" statusDotColor="muted">
        <ul className="space-y-1 text-sm">
          {sorted.slice(0, 8).map((p, i) => (
            <li key={i} className="flex items-center justify-between gap-2">
              <span className="truncate text-text">{p.name}</span>
              <NumberDisplay value={p.weight_pct} format="percent" />
            </li>
          ))}
        </ul>
      </Panel>
      <p className="md:col-span-2 text-xs text-text-label">
        beta vs spy, max drawdown, and value-at-risk need a returns series (pending).
      </p>
    </div>
  )
}

// 6. Scenarios — portfolio_scenario skill (background)
function ScenariosTab() {
  const runSkill = useRunSkill()
  const [text, setText] = useState("")

  function run() {
    const scenario = text.trim()
    if (!scenario) return
    runSkill.mutate(
      { skill: "portfolio_scenario", args: { scenario_description: scenario }, label: "Portfolio scenario" },
      {
        onSuccess: (r) => {
          setText("")
          toast.success("started in background — see background runs", r.run_id)
        },
        onError: (e) => toast.error("failed to start", String(e)),
      },
    )
  }

  return (
    <Panel title="what-if scenario" statusDotColor="accent">
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="describe a what-if — claude runs it against your current holdings..."
        rows={4}
      />
      <div className="mt-2 flex flex-wrap gap-1.5">
        {SCENARIO_EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => setText(ex)}
            className="rounded-sm border border-border px-2 py-1 text-xs text-text-secondary hover:border-accent-dim hover:text-text"
          >
            {ex}
          </button>
        ))}
      </div>
      <div className="mt-3 flex justify-end">
        <Button onClick={run} disabled={!text.trim() || runSkill.isPending}>
          run scenario
        </Button>
      </div>
    </Panel>
  )
}

// 7. Tax — harvest candidates = positions at a loss
function TaxTab({ holdings, loading }: { holdings: HoldingRow[]; loading: boolean }) {
  if (loading) return <Skeleton className="h-40" />
  const losers = holdings
    .map((h) => ({
      name: pickStr(h, "Position"),
      pnl: pick(h, "% Since Bought"),
      value: pick(h, "Market Value"),
    }))
    .filter((h) => (h.pnl ?? 0) < 0)
    .sort((a, b) => (a.pnl ?? 0) - (b.pnl ?? 0))

  return (
    <div className="space-y-4">
      <Panel title="harvest opportunities" meta="positions at a loss" statusDotColor="warning">
        {losers.length === 0 ? (
          <p className="text-sm text-text-label">no positions currently at a loss</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {losers.map((h, i) => (
              <li key={i} className="flex items-center justify-between gap-2">
                <span className="truncate text-text">{h.name}</span>
                <span className="flex items-center gap-3">
                  <span className="font-mono text-xs text-text-secondary">
                    {formatCurrency(h.value)}
                  </span>
                  <NumberDisplay value={h.pnl} format="percent" signed />
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Panel title="realized gains / losses" statusDotColor="muted">
        <p className="text-sm text-text-label">
          realized-gains tracker + abgeltungsteuer + 12-month holding period need a
          transaction-lot source (pending)
        </p>
      </Panel>
    </div>
  )
}
