import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Collapsible } from "@/components/ui/collapsible"
import { NumberDisplay } from "@/components/ui/number-display"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { FinanceHoldingsTable } from "@/components/finance/finance-holdings-table"
import { TransactionForm } from "@/components/finance/transaction-form"
import { BucketAllocation } from "@/components/finance/bucket-allocation"
import { OptimizationTab } from "@/components/finance/optimization-panel"
import { FactorsTab } from "@/components/finance/factors-panel"
import { DecisionsTab } from "@/components/finance/decisions-panel"
import { JournalTab } from "@/components/finance/journal-panel"
import { WatchlistComparisonTab } from "@/components/finance/watchlist-comparison"
import { ScenarioTools } from "@/components/finance/scenarios-panel"
import {
  AllocationBar,
  CategoryDonut,
  PerformanceArea,
} from "@/components/charts/finance-charts"
import {
  BestWorstBars,
  CorrelationHeatmap,
  CumulativeReturnChart,
  RollingSharpeChart,
} from "@/components/charts/finance-analytics-charts"
import { CHART_COLORS } from "@/components/charts/theme"
import {
  usePortfolioSnapshot,
  usePortfolioPerformance,
  usePortfolioAllocations,
  useFinanceHoldings,
  useFinancePerformance,
  useFinanceCumulative,
  useFinanceRolling,
  useFinanceRisk,
  useFinanceCorrelation,
  type HoldingRow,
  type RiskResponse,
} from "@/hooks/useFinance"
import { useRunSkill } from "@/hooks/useSkills"
import { toast } from "@/lib/toast-store"
import { formatCurrency } from "@/lib/utils"

const BENCHMARKS = [
  { key: "MSCI_WORLD", label: "MSCI World" },
  { key: "SPY", label: "S&P 500" },
  { key: "DAX", label: "DAX 40" },
  { key: "STOXX_600", label: "STOXX 600" },
]
const PERIODS = ["ytd", "1y", "3y", "5y", "all"]

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
  const holdings = snap.data?.holdings ?? []

  // Tab is URL-driven so Home's decision-alerts panel can deep-link a tab.
  const [params, setParams] = useSearchParams()
  const tab = params.get("tab") ?? "holdings"
  const setTab = (v: string) =>
    setParams(v === "holdings" ? {} : { tab: v }, { replace: true })

  return (
    <div className="min-h-screen bg-bg text-text p-6">
      <div className="mx-auto max-w-[1400px] space-y-5">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">portfolio workspace</h1>
          <Link to="/portfolio" className="font-mono text-xs text-text-secondary hover:text-accent">
            ← portfolio
          </Link>
        </div>

        {/* 4-bucket allocation vs target — always visible above the tabs. */}
        <BucketAllocation />

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="holdings">holdings</TabsTrigger>
            <TabsTrigger value="allocations">allocations</TabsTrigger>
            <TabsTrigger value="optimization">optimization</TabsTrigger>
            <TabsTrigger value="factors">factors</TabsTrigger>
            <TabsTrigger value="performance">performance</TabsTrigger>
            <TabsTrigger value="attribution">attribution</TabsTrigger>
            <TabsTrigger value="risk">risk</TabsTrigger>
            <TabsTrigger value="scenarios">scenarios</TabsTrigger>
            <TabsTrigger value="tax">tax</TabsTrigger>
            <TabsTrigger value="decisions">decisions</TabsTrigger>
            <TabsTrigger value="journal">journal</TabsTrigger>
            <TabsTrigger value="watchlist">watchlist</TabsTrigger>
          </TabsList>

          {/* 1. Holdings — real per-position metrics + log-transaction form. */}
          <TabsContent value="holdings">
            <HoldingsTab />
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
              </Panel>
            </div>
          </TabsContent>

          {/* Optimization — efficient frontier, optimal portfolios, BL. */}
          <TabsContent value="optimization">
            <OptimizationTab />
          </TabsContent>

          {/* Factors — Fama-French 3-factor regression + decomposition. */}
          <TabsContent value="factors">
            <FactorsTab />
          </TabsContent>

          {/* 3. Performance — real cumulative + rolling sharpe + best/worst. */}
          <TabsContent value="performance">
            <PerformanceTab />
          </TabsContent>

          {/* 4. Attribution */}
          <TabsContent value="attribution">
            <AttributionTab holdings={holdings} loading={snap.isLoading} />
          </TabsContent>

          {/* 5. Risk — real volatility / ratios / drawdown / VaR / correlation. */}
          <TabsContent value="risk">
            <RiskTab />
          </TabsContent>

          {/* 6. Scenarios */}
          <TabsContent value="scenarios">
            <ScenariosTab />
          </TabsContent>

          {/* 7. Tax */}
          <TabsContent value="tax">
            <TaxTab holdings={holdings} loading={snap.isLoading} />
          </TabsContent>

          {/* 8. Decisions — sizing, rebalancing, harvest, concentration (Phase 15c). */}
          <TabsContent value="decisions">
            <DecisionsTab />
          </TabsContent>

          {/* 9. Journal — decision log, hypothesis hit rate, anti-portfolio (Phase 15d). */}
          <TabsContent value="journal">
            <JournalTab />
          </TabsContent>

          {/* 10. Watchlist comparison — same metrics as holdings + add simulation (Phase 15d). */}
          <TabsContent value="watchlist">
            <WatchlistComparisonTab />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

// 1. Holdings — transaction-driven holdings with per-position risk.
function HoldingsTab() {
  const { data, isLoading } = useFinanceHoldings()
  const rows = data?.holdings ?? []

  return (
    <div className="space-y-4">
      <Panel
        title="holdings"
        meta={data ? `${rows.length} positions · ${formatCurrency(data.total_market_value)}` : undefined}
        statusDotColor="accent"
      >
        {isLoading ? <Skeleton className="h-40" /> : <FinanceHoldingsTable holdings={rows} />}
        <p className="mt-2 text-xs text-text-label">
          sharpe / vol / beta are per-position from each ticker's daily return history;
          beta vs s&amp;p 500.
        </p>
      </Panel>

      <Collapsible title="log a transaction" meta="buy / sell / dividend">
        <TransactionForm />
      </Collapsible>
    </div>
  )
}

// 3. Performance tab.
function PerformanceTab() {
  const [period, setPeriod] = useState("1y")
  const [benchmark, setBenchmark] = useState("MSCI_WORLD")
  const metrics = useFinancePerformance(period, benchmark)
  const cumulative = useFinanceCumulative(period, benchmark)
  const rolling = useFinanceRolling(252, benchmark)
  const m = metrics.data

  const bestWorst = m?.best_worst
  const bwData = bestWorst
    ? [
        { label: "best month", v: bestWorst.best_month?.return },
        { label: "worst month", v: bestWorst.worst_month?.return },
        { label: "best quarter", v: bestWorst.best_quarter?.return },
        { label: "worst quarter", v: bestWorst.worst_quarter?.return },
        { label: "best year", v: bestWorst.best_year?.return },
        { label: "worst year", v: bestWorst.worst_year?.return },
      ]
        .filter((d) => typeof d.v === "number")
        .map((d) => ({ label: d.label, return: d.v as number }))
    : []

  return (
    <div className="space-y-4">
      {/* Controls. */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="w-32">
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {PERIODS.map((p) => (
                <SelectItem key={p} value={p}>{p}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="w-44">
          <Select value={benchmark} onValueChange={setBenchmark}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {BENCHMARKS.map((b) => (
                <SelectItem key={b.key} value={b.key}>{b.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Headline metrics. */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Metric label="twr" value={m?.time_weighted_return} pct />
        <Metric label="mwr (irr)" value={m?.money_weighted_return} pct />
        <Metric label="ann. return" value={m?.annualized_return} pct />
        <Metric label="alpha" value={m?.alpha} pct />
        <Metric label="beta" value={m?.beta} ratio />
        <Metric label="info ratio" value={m?.information_ratio} ratio />
      </div>

      <Panel
        title="cumulative return vs benchmark"
        meta={m?.benchmark_name ?? undefined}
        statusDotColor="accent"
      >
        {cumulative.isLoading ? (
          <Skeleton className="h-72" />
        ) : (cumulative.data?.series.length ?? 0) === 0 ? (
          <p className="text-sm text-text-label">no return series for this period</p>
        ) : (
          <CumulativeReturnChart
            data={cumulative.data!.series}
            benchmarkName={cumulative.data!.benchmark_name ?? "benchmark"}
          />
        )}
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="rolling sharpe" meta="252d window" statusDotColor="accent">
          {rolling.isLoading ? (
            <Skeleton className="h-56" />
          ) : (rolling.data?.series.length ?? 0) === 0 ? (
            <p className="text-sm text-text-label">not enough history</p>
          ) : (
            <RollingSharpeChart data={rolling.data!.series} />
          )}
        </Panel>
        <Panel title="best / worst periods" meta="total return" statusDotColor="muted">
          {metrics.isLoading ? (
            <Skeleton className="h-56" />
          ) : bwData.length === 0 ? (
            <p className="text-sm text-text-label">no data</p>
          ) : (
            <BestWorstBars data={bwData} />
          )}
        </Panel>
      </div>

      <Panel title="contribution" meta={`${period} · per position`} statusDotColor="muted">
        {(m?.contribution?.length ?? 0) === 0 ? (
          <p className="text-sm text-text-label">no contribution data</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {m!.contribution!.map((c) => (
              <li key={c.ticker} className="flex items-center justify-between gap-2">
                <span className="text-text">{c.ticker}</span>
                <span className="flex items-center gap-4">
                  <span className="font-mono text-xs text-text-secondary">
                    w {(c.weight * 100).toFixed(1)}%
                  </span>
                  <NumberDisplay value={c.contribution * 100} format="percent" signed decimals={2} />
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
      {m?.win_rate != null && (
        <p className="text-xs text-text-label">
          win rate vs benchmark (monthly): {(m.win_rate * 100).toFixed(0)}%
        </p>
      )}
    </div>
  )
}

// 5. Risk tab — real metrics.
function RiskTab() {
  const [benchmark, setBenchmark] = useState("MSCI_WORLD")
  const risk = useFinanceRisk(benchmark)
  const corr = useFinanceCorrelation()
  const r: RiskResponse | undefined = risk.data

  if (risk.isLoading) return <Skeleton className="h-64" />
  if (!r?.available) return <p className="text-sm text-text-label">{r?.reason ?? "no risk data"}</p>

  const dd = r.max_drawdown
  return (
    <div className="space-y-4">
      <div className="flex w-44 items-center">
        <Select value={benchmark} onValueChange={setBenchmark}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            {BENCHMARKS.map((b) => (
              <SelectItem key={b.key} value={b.key}>{b.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Ratios + vol. */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        <Metric label="sharpe" value={r.sharpe} ratio />
        <Metric label="sortino" value={r.sortino} ratio />
        <Metric label="calmar" value={r.calmar} ratio />
        <Metric label="beta" value={r.beta} ratio />
        <Metric label="vol 30d" value={r.volatility?.rolling_30d} pct />
        <Metric label="vol 90d" value={r.volatility?.rolling_90d} pct />
        <Metric label="vol 12m" value={r.volatility?.rolling_12m} pct />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Max drawdown. */}
        <Panel title="max drawdown" statusDotColor="danger">
          <NumberDisplay
            value={dd?.magnitude != null ? dd.magnitude * 100 : null}
            format="percent"
            decimals={1}
            className="text-2xl text-danger"
          />
          <div className="mt-2 space-y-0.5 text-xs text-text-secondary">
            <Row label="peak" value={dd?.peak_date} />
            <Row label="trough" value={dd?.trough_date} />
            <Row label="recovery" value={dd?.recovery_date ?? "not recovered"} />
            <Row label="peak→trough" value={dd?.duration_days != null ? `${dd.duration_days} days` : "—"} />
          </div>
        </Panel>

        {/* VaR + CVaR. */}
        <Panel title="value at risk" meta="daily" statusDotColor="warning">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-text-label">
                <th className="py-1 font-normal">method</th>
                <th className="py-1 text-right font-normal">95%</th>
                <th className="py-1 text-right font-normal">99%</th>
              </tr>
            </thead>
            <tbody className="font-mono tabular-nums">
              <VarRow label="parametric" a={r.var?.parametric_95} b={r.var?.parametric_99} />
              <VarRow label="historical" a={r.var?.historical_95} b={r.var?.historical_99} />
              <VarRow label="cornish-fisher" a={r.var?.cornish_fisher_95} b={r.var?.cornish_fisher_99} />
              <VarRow label="cvar (es)" a={r.expected_shortfall?.cvar_95} b={r.expected_shortfall?.cvar_99} />
            </tbody>
          </table>
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Correlation heatmap. */}
        <Panel title="correlation matrix" meta="daily returns" statusDotColor="accent">
          {corr.isLoading ? (
            <Skeleton className="h-40" />
          ) : (
            <CorrelationHeatmap tickers={corr.data?.tickers ?? []} matrix={corr.data?.matrix ?? []} />
          )}
        </Panel>

        {/* Concentration. */}
        <Panel title="concentration" statusDotColor={(r.concentration?.top_3_weight ?? 0) > 0.6 ? "danger" : "accent"}>
          <div className="grid grid-cols-2 gap-3">
            <ConcMetric label="herfindahl" value={r.concentration?.herfindahl_index?.toFixed(3)} />
            <ConcMetric label="effective bets" value={r.concentration?.effective_n_bets?.toFixed(2)} />
            <ConcMetric label="top-1 weight" value={fmtPct(r.concentration?.top_1_weight)} />
            <ConcMetric label="top-3 weight" value={fmtPct(r.concentration?.top_3_weight)} />
            <ConcMetric label="top-5 weight" value={fmtPct(r.concentration?.top_5_weight)} />
          </div>
        </Panel>
      </div>
    </div>
  )
}

function fmtPct(v: number | null | undefined): string {
  return v == null ? "—" : `${(v * 100).toFixed(1)}%`
}

function Metric({ label, value, pct, ratio }: { label: string; value?: number | null; pct?: boolean; ratio?: boolean }) {
  return (
    <Panel title={label} statusDotColor="muted">
      {value == null ? (
        <span className="font-mono text-xl text-text-label">—</span>
      ) : pct ? (
        <NumberDisplay value={value * 100} format="percent" decimals={1} emphasized className="text-xl" />
      ) : ratio ? (
        <span className="font-mono text-xl font-medium tabular-nums text-text">{value.toFixed(2)}</span>
      ) : (
        <NumberDisplay value={value} className="text-xl" />
      )}
    </Panel>
  )
}

function Row({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-text-label">{label}</span>
      <span className="font-mono text-text-secondary">{value ?? "—"}</span>
    </div>
  )
}

function VarRow({ label, a, b }: { label: string; a?: number | null; b?: number | null }) {
  const fmt = (v?: number | null) => (v == null ? "—" : `${(v * 100).toFixed(2)}%`)
  return (
    <tr>
      <td className="py-1 font-sans text-text-secondary">{label}</td>
      <td className="py-1 text-right text-danger">{fmt(a)}</td>
      <td className="py-1 text-right text-danger">{fmt(b)}</td>
    </tr>
  )
}

function ConcMetric({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <div className="label mb-0.5">{label}</div>
      <span className="font-mono text-lg font-medium tabular-nums text-text">{value ?? "—"}</span>
    </div>
  )
}

// 4. Attribution — derived: contribution = market value × (%YTD / 100).
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
        estimated as market value × % ytd from the legacy snapshot. precise
        contribution is on the performance tab.
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

// 6. Scenarios — real quantitative tools (market shock, what-if, fx) + a
// free-form Claude scenario for anything the structured tools don't cover.
function ScenariosTab() {
  return (
    <div className="space-y-4">
      <ScenarioTools />
      <Collapsible title="ask claude a free-form scenario" meta="deeper / qualitative">
        <ClaudeScenario />
      </Collapsible>
    </div>
  )
}

function ClaudeScenario() {
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
    <div>
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
    </div>
  )
}

// 7. Tax — harvest candidates = positions at a loss.
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
                  <span className="font-mono text-xs text-text-secondary">{formatCurrency(h.value)}</span>
                  <NumberDisplay value={h.pnl} format="percent" signed />
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Panel title="realized gains / losses" statusDotColor="muted">
        <p className="text-sm text-text-label">
          realized-gains tracker + abgeltungsteuer + 12-month holding period are a
          later phase (15c).
        </p>
      </Panel>
    </div>
  )
}
