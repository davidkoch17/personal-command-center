import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Collapsible } from "@/components/ui/collapsible"
import { NumberDisplay } from "@/components/ui/number-display"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { MetricPanel } from "@/components/finance/metric-panel"
import { HoldingsTable } from "@/components/finance/holdings-table"
import { BucketAllocation } from "@/components/finance/bucket-allocation"
import { DecisionAlerts } from "@/components/finance/decision-alerts"
import { TaxIntegrationPanels } from "@/components/finance/tax-panel"
import {
  HitRatePanel,
  AntiPortfolioPanel,
  DecisionList,
  DecisionLogForm,
} from "@/components/finance/journal-panel"
import { InfoBarrierBanner } from "@/components/ui/info-barrier-banner"
import {
  IncomeExpenseBar,
  CategoryDonut,
  NetWorthTrendLine,
} from "@/components/charts/finance-charts"
import { Watchlist } from "@/_archive/watchlist"
import {
  usePortfolioSnapshot,
  usePortfolioPerformance,
  useMoneySnapshot,
  useMoneyCashflow,
  useMoneyCategories,
  useNetWorthHistory,
  useCapitalAllocation,
  useAfterTaxReturn,
  useWealthConfig,
  type AfterTaxReturnResponse,
  type InsuranceEntry,
  type PkvDecision,
  type AccountEntry,
} from "@/hooks/useFinance"
import { useNotgroschen } from "@/hooks/useHome"
import { useTravel } from "@/hooks/useCalendar"
import { useHardDates } from "@/hooks/useTasks"
import { formatBoth } from "@/lib/dates"
import { formatCurrency } from "@/lib/utils"
import { lastCategoryBreakdown } from "@/lib/money"

/**
 * Wealth page (v2 Page 3). One hub merging Portfolio + Watchlist + Decision
 * Journal + Money. The net-worth number is the headline (always visible, with
 * the NEW net-worth-over-time trend, N1); depth lives behind five tabs and the
 * deep-dive workspaces (Portfolio / Money / Watchlist-ticker) open in new tabs.
 * Wires the two built-but-unused endpoints: capital-allocation/suggest (D1) and
 * tax/after-tax-return (D2). All monetary values in EUR.
 */
export function Wealth() {
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">wealth</h1>
        <div className="flex gap-2">
          <Button asChild variant="secondary" size="sm">
            <a href="/workspace/portfolio" target="_blank" rel="noopener noreferrer">
              portfolio workspace ↗
            </a>
          </Button>
          <Button asChild variant="secondary" size="sm">
            <a href="/workspace/money" target="_blank" rel="noopener noreferrer">
              money workspace ↗
            </a>
          </Button>
        </div>
      </div>

      <NetWorthHeadline />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">overview</TabsTrigger>
          <TabsTrigger value="portfolio">portfolio</TabsTrigger>
          <TabsTrigger value="watchlist">watchlist</TabsTrigger>
          <TabsTrigger value="cash-tax">cash &amp; tax</TabsTrigger>
          <TabsTrigger value="decisions">decisions</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <OverviewTab />
        </TabsContent>
        <TabsContent value="portfolio">
          <PortfolioTab />
        </TabsContent>
        <TabsContent value="watchlist">
          <Watchlist />
        </TabsContent>
        <TabsContent value="cash-tax">
          <CashTaxTab />
        </TabsContent>
        <TabsContent value="decisions">
          <DecisionsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}

// --- Headline: net worth + trend + deployable cash + suggestion + Notgroschen --

function NetWorthHeadline() {
  const snap = useMoneySnapshot()
  const history = useNetWorthHistory()
  const alloc = useCapitalAllocation()
  const notgroschen = useNotgroschen()

  const series = (history.data?.history ?? []).map((p) => ({ month: p.month, total: p.total }))
  const change = history.data?.change_since_start
  const topSuggestion = alloc.data?.suggestions?.[0]
  const ng = notgroschen.data

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {/* Net worth + trend — the one number that matters. */}
      <Panel
        title="net worth"
        statusDotColor="success"
        meta={history.data ? `${history.data.count} mo` : undefined}
        className="lg:col-span-2"
      >
        <div className="mb-3 flex flex-wrap items-baseline gap-x-6 gap-y-1">
          {snap.isLoading ? (
            <Skeleton className="h-9 w-44" />
          ) : (
            <NumberDisplay
              value={snap.data?.net_worth}
              format="currency"
              emphasized
              animate
              className="text-3xl"
            />
          )}
          {change != null && (
            <span className="flex items-baseline gap-1.5 text-sm">
              <span className="label">since start</span>
              <NumberDisplay value={change} format="currency" signed />
            </span>
          )}
        </div>
        {history.isLoading ? (
          <Skeleton className="h-56" />
        ) : series.length === 0 ? (
          <p className="text-sm text-text-label">
            no net-worth history yet — a snapshot is recorded on each finance refresh.
          </p>
        ) : (
          <NetWorthTrendLine data={series} />
        )}
      </Panel>

      {/* Deployable cash + suggestion + Notgroschen. */}
      <div className="space-y-4">
        <Panel
          title="deployable cash"
          statusDotColor="accent"
          meta={alloc.data ? "capital allocation" : undefined}
        >
          {alloc.isLoading ? (
            <Skeleton className="h-7 w-28" />
          ) : (
            <NumberDisplay
              value={alloc.data?.cash_deployable}
              format="currency"
              emphasized
              className="text-2xl"
            />
          )}
          <div className="mt-2 border-t border-border pt-2">
            <div className="label mb-1">deployment suggestion</div>
            {alloc.isLoading ? (
              <Skeleton className="h-8" />
            ) : topSuggestion ? (
              <div className="flex items-center justify-between gap-2 text-sm">
                <span className="text-text">{topSuggestion.label}</span>
                <span className="font-mono text-success tabular-nums">
                  +{formatCurrency(topSuggestion.suggested_deploy_eur)}
                </span>
              </div>
            ) : (
              <p className="text-xs text-text-label">
                {alloc.data && alloc.data.cash_deployable <= 0
                  ? "no deployable cash"
                  : "buckets within target — nothing to deploy"}
              </p>
            )}
            {topSuggestion?.rationale && (
              <p className="mt-0.5 text-xs text-text-label">{topSuggestion.rationale}</p>
            )}
          </div>
        </Panel>

        <Panel
          title="notgroschen"
          statusDotColor={ng?.phase === 2 ? "success" : "accent"}
        >
          {notgroschen.isLoading ? (
            <Skeleton className="h-14" />
          ) : ng?.phase === 2 ? (
            <>
              <div className="label mb-0.5">notgroschen full — depot funding</div>
              <NumberDisplay value={ng.depot_invested} format="currency" emphasized className="text-xl" />
              <span className="ml-2 text-xs text-text-secondary">invested (phase 2)</span>
            </>
          ) : (
            <>
              <div className="mb-1 flex items-baseline justify-between">
                <span className="label">phase 1 → €4,000 tagesgeld</span>
                <span className="font-mono text-xs text-text-secondary tabular-nums">
                  {ng?.cash_balance != null ? formatCurrency(ng.cash_balance) : "—"} /{" "}
                  {formatCurrency(ng?.target ?? 4000)}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-bg-panel-hover">
                <div
                  className="h-full rounded-full bg-accent transition-all"
                  style={{ width: `${Math.round((ng?.pct ?? 0) * 100)}%` }}
                />
              </div>
              <div className="mt-1 font-mono text-xs text-text-secondary tabular-nums">
                {Math.round((ng?.pct ?? 0) * 100)}%
              </div>
            </>
          )}
        </Panel>
      </div>
    </div>
  )
}

// --- Overview tab ------------------------------------------------------------

function OverviewTab() {
  return (
    <div className="space-y-4">
      <DecisionAlerts />
      <BucketAllocation />
      <p className="text-xs text-text-label">
        net-worth trend + deployable cash live in the headline above. allocation drift vs the
        4-bucket targets (Investment_Philosophy.md § 0) and active decision alerts here; full
        analytics in the portfolio workspace.
      </p>
    </div>
  )
}

// --- Portfolio tab -----------------------------------------------------------

function PortfolioTab() {
  const snap = usePortfolioSnapshot()
  const ytd = usePortfolioPerformance("ytd")

  return (
    <div className="space-y-4">
      <InfoBarrierBanner message="restricted-sector names may be involved" />

      <div className="flex items-center justify-end">
        <Button asChild variant="secondary" size="sm">
          <a href="/workspace/portfolio" target="_blank" rel="noopener noreferrer">
            full analytics workspace ↗
          </a>
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricPanel
          label="total value"
          value={
            snap.isLoading ? (
              <Skeleton className="h-7 w-28" />
            ) : (
              <NumberDisplay value={snap.data?.total_value} format="currency" emphasized animate />
            )
          }
          caption={`${snap.data?.position_count ?? 0} positions`}
        />
        <MetricPanel
          label="p&l today"
          dotColor="muted"
          value={<span className="text-text-label">—</span>}
          caption="no intraday source"
        />
        <MetricPanel
          label="p&l ytd"
          dotColor={(ytd.data?.change_pct ?? 0) >= 0 ? "success" : "danger"}
          value={
            ytd.isLoading ? (
              <Skeleton className="h-7 w-20" />
            ) : (
              <NumberDisplay value={ytd.data?.change_pct} format="percent" signed />
            )
          }
        />
        <MetricPanel
          label="cash deployable"
          dotColor="success"
          value={
            snap.isLoading ? (
              <Skeleton className="h-7 w-28" />
            ) : (
              <NumberDisplay value={snap.data?.cash_deployable} format="currency" />
            )
          }
        />
      </div>

      <Panel
        title="holdings"
        meta={`${snap.data?.holdings.length ?? 0} positions`}
        statusDotColor="accent"
      >
        {snap.isLoading ? (
          <Skeleton className="h-40" />
        ) : snap.isError ? (
          <p className="text-text-secondary">could not load holdings. backend on :8000?</p>
        ) : (
          <HoldingsTable holdings={snap.data?.holdings ?? []} />
        )}
      </Panel>
    </div>
  )
}

// --- Cash & Tax tab ----------------------------------------------------------

function CashTaxTab() {
  const snap = useMoneySnapshot()
  const cashflow = useMoneyCashflow(6)
  const categories = useMoneyCategories(6)
  const travel = useTravel()
  const hardDates = useHardDates()
  const breakdown = lastCategoryBreakdown(categories.data?.categories ?? [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end">
        <Button asChild variant="secondary" size="sm">
          <a href="/workspace/money" target="_blank" rel="noopener noreferrer">
            money workspace ↗
          </a>
        </Button>
      </div>

      {/* Money snapshot */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricPanel
          label="cash"
          value={
            snap.isLoading ? <Skeleton className="h-7 w-28" /> : (
              <NumberDisplay value={snap.data?.cash_balance} format="currency" emphasized animate />
            )
          }
        />
        <MetricPanel
          label="net worth"
          dotColor="success"
          value={
            snap.isLoading ? <Skeleton className="h-7 w-28" /> : (
              <NumberDisplay value={snap.data?.net_worth} format="currency" emphasized animate />
            )
          }
        />
        <MetricPanel
          label="monthly burn"
          dotColor="warning"
          value={
            snap.isLoading ? <Skeleton className="h-7 w-24" /> : (
              <NumberDisplay value={snap.data?.monthly_burn} format="currency" />
            )
          }
        />
        <MetricPanel
          label="runway"
          dotColor="accent"
          value={
            snap.isLoading ? <Skeleton className="h-7 w-16" /> : (
              <span>
                <NumberDisplay value={snap.data?.runway_months} decimals={1} />
                <span className="ml-1 text-sm text-text-secondary">mo</span>
              </span>
            )
          }
        />
      </div>

      {/* Cashflow + spend categories */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="income vs expenses" meta="last 6 months" statusDotColor="accent">
          {cashflow.isLoading ? (
            <Skeleton className="h-64" />
          ) : (
            <IncomeExpenseBar data={cashflow.data?.cashflow ?? []} />
          )}
        </Panel>
        <Panel title="spending breakdown" meta="last month" statusDotColor="accent">
          {categories.isLoading ? (
            <Skeleton className="h-64" />
          ) : breakdown.length === 0 ? (
            <p className="text-sm text-text-label">no category data</p>
          ) : (
            <CategoryDonut data={breakdown} />
          )}
        </Panel>
      </div>

      {/* Big upcoming */}
      <Panel title="big upcoming" statusDotColor="warning">
        <ul className="space-y-1.5 text-sm">
          {(hardDates.data ?? []).map((d) => (
            <li key={`${d.date}-${d.label}`} className="flex items-center justify-between gap-2">
              <span className="text-text">{d.label}</span>
              <span className="font-mono text-xs text-accent tabular-nums">{formatBoth(d.date)}</span>
            </li>
          ))}
          {(travel.data?.trips ?? []).map((t, i) => (
            <li key={`trip-${i}`} className="flex items-center justify-between gap-2">
              <span className="text-text">{String(t.destination ?? t.title ?? "trip")}</span>
              <span className="font-mono text-xs text-text-secondary">
                {t.days_until != null ? `in ${t.days_until}d` : String(t.date ?? "")}
              </span>
            </li>
          ))}
        </ul>
      </Panel>

      {/* Tax: annual Abgeltungsteuer + crypto Spekulationsfrist + capital allocation */}
      <TaxIntegrationPanels />

      {/* D2 — after-tax-return (wires the built-but-unused endpoint) */}
      <AfterTaxReturnPanel />

      {/* Insurance · PKV · Mehrkontenmodell */}
      <WealthReference />
    </div>
  )
}

function AfterTaxReturnPanel() {
  const calc = useAfterTaxReturn()
  const [gross, setGross] = useState("")
  const [days, setDays] = useState("")
  const [assetType, setAssetType] = useState("stock")
  const [church, setChurch] = useState(false)
  const [result, setResult] = useState<AfterTaxReturnResponse | null>(null)

  function run() {
    calc.mutate(
      {
        gross_return: parseFloat(gross) || 0,
        holding_period_days: parseInt(days) || 0,
        asset_type: assetType,
        church_tax: church,
      },
      { onSuccess: (r) => setResult(r) },
    )
  }

  return (
    <Panel title="after-tax return" meta="net of Abgeltungsteuer (D2)" statusDotColor="accent">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-40">
          <div className="label mb-1">gross return %</div>
          <Input mono type="number" value={gross} onChange={(e) => setGross(e.target.value)} placeholder="e.g. 12" />
        </div>
        <div className="w-40">
          <div className="label mb-1">holding period (days)</div>
          <Input mono type="number" value={days} onChange={(e) => setDays(e.target.value)} placeholder="e.g. 400" />
        </div>
        <div className="w-40">
          <div className="label mb-1">asset type</div>
          <select
            value={assetType}
            onChange={(e) => setAssetType(e.target.value)}
            className="h-9 w-full rounded-sm border border-border bg-bg-panel px-2 text-sm text-text"
          >
            <option value="stock">stock / ETF</option>
            <option value="crypto">crypto</option>
          </select>
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm text-text-secondary">
          <input type="checkbox" checked={church} onChange={(e) => setChurch(e.target.checked)} />
          church tax
        </label>
        <Button disabled={calc.isPending} onClick={run}>
          calculate
        </Button>
      </div>

      <div className="mt-4">
        {calc.isPending ? (
          <Skeleton className="h-16" />
        ) : result == null ? (
          <p className="text-sm text-text-label">
            crypto held ≥ 365 days is tax-free (§23 EStG); stocks/ETFs incur ~26.4% Abgeltungsteuer + soli.
          </p>
        ) : (
          <div className="flex flex-wrap items-end gap-8">
            <div>
              <div className="label mb-0.5">after-tax return</div>
              <NumberDisplay value={result.after_tax_return} format="percent" emphasized className="text-2xl" />
            </div>
            <div>
              <div className="label mb-0.5">gross return</div>
              <NumberDisplay value={result.gross_return} format="percent" className="text-xl" />
            </div>
            <div>
              <div className="label mb-0.5">effective tax rate</div>
              <NumberDisplay value={result.effective_rate * 100} format="percent" decimals={2} className="text-xl" />
            </div>
            {result.tax_free && (
              <span className="pb-1 font-mono text-sm text-success">tax-free (12-mo hold) ✓</span>
            )}
          </div>
        )}
      </div>
    </Panel>
  )
}

function WealthReference() {
  const { data, isLoading } = useWealthConfig()

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <InsuranceTracker entries={data?.insurance ?? []} loading={isLoading} />
        <PkvRecord record={data?.pkv_decision} loading={isLoading} />
      </div>
      <AccountStructure accounts={data?.accounts ?? []} loading={isLoading} />
      {data?.source === "default-template" && (
        <p className="text-xs text-text-label">
          structural template — fill provider/premium/balance detail in
          <span className="mx-1 font-mono">data/wealth_config.json</span>
          (no figures are invented here).
        </p>
      )}
    </div>
  )
}

function InsuranceTracker({ entries, loading }: { entries: InsuranceEntry[]; loading: boolean }) {
  return (
    <Panel title="insurance tracker" meta="KV · BU · third" statusDotColor="accent">
      {loading ? (
        <Skeleton className="h-32" />
      ) : (
        <ul className="space-y-2.5">
          {entries.map((e) => (
            <li key={e.key} className="border-b border-border/40 pb-2 last:border-0">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-text">{e.type}</span>
                {e.status === "placeholder" ? (
                  <span className="font-mono text-xs text-warning">to record</span>
                ) : (
                  <span className="font-mono text-sm text-text tabular-nums">
                    {e.monthly_eur != null ? `${formatCurrency(e.monthly_eur)}/mo` : "—"}
                  </span>
                )}
              </div>
              {e.provider && <p className="text-xs text-text-secondary">{e.provider}</p>}
              {e.notes && <p className="mt-0.5 text-xs text-text-label">{e.notes}</p>}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

function PkvRecord({ record, loading }: { record: PkvDecision | undefined; loading: boolean }) {
  return (
    <Panel
      title="pkv decision record"
      meta={record?.status === "unrecorded" ? "unrecorded" : record?.outcome ?? undefined}
      statusDotColor={record?.status === "unrecorded" ? "warning" : "success"}
    >
      {loading ? (
        <Skeleton className="h-32" />
      ) : record?.status === "unrecorded" ? (
        <div className="space-y-1">
          <p className="text-sm text-warning">no PKV decision recorded yet</p>
          <p className="text-xs text-text-label">{record?.notes}</p>
        </div>
      ) : (
        <div className="space-y-1.5 text-sm">
          <div className="flex justify-between gap-2">
            <span className="text-text-secondary">outcome</span>
            <span className="text-text">{record?.outcome ?? "—"}</span>
          </div>
          <div className="flex justify-between gap-2">
            <span className="text-text-secondary">decided on</span>
            <span className="font-mono text-xs text-text-secondary">{record?.decided_on ?? "—"}</span>
          </div>
          {record?.rationale && <p className="text-xs text-text-label">{record.rationale}</p>}
        </div>
      )}
    </Panel>
  )
}

function AccountStructure({ accounts, loading }: { accounts: AccountEntry[]; loading: boolean }) {
  return (
    <Panel title="account structure" meta="Mehrkontenmodell" statusDotColor="accent">
      {loading ? (
        <Skeleton className="h-28" />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {accounts.map((a) => (
            <div key={a.key} className="rounded-sm border border-border bg-bg-panel p-2.5">
              <div className="text-sm text-text">{a.label}</div>
              <div className="mt-0.5 text-xs text-text-label">{a.purpose}</div>
              <div className="mt-1.5 font-mono text-xs text-text-secondary">
                {a.bank ?? "bank: to record"}
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  )
}

// --- Decisions tab -----------------------------------------------------------

function DecisionsTab() {
  return (
    <div className="space-y-4">
      <DecisionAlerts />
      <div className="grid gap-4 lg:grid-cols-2">
        <HitRatePanel />
        <AntiPortfolioPanel />
      </div>
      <DecisionList filterable />
      {/* The real Decision-Journal entry point (was orphaned before v2). */}
      <Collapsible title="log a decision" meta="thesis · conviction · pre-mortem" defaultOpen>
        <DecisionLogForm />
      </Collapsible>
    </div>
  )
}
