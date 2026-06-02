import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { NumberDisplay } from "@/components/ui/number-display"
import {
  useAnnualTaxEstimate,
  useFinanceHoldings,
  useHoldingPeriod,
  useCapitalAllocation,
  type AnnualTaxResponse,
} from "@/hooks/useFinance"
import { formatCurrency } from "@/lib/utils"

/** Money-workspace Tax tab integration (Phase 15d): annual Abgeltungsteuer
 *  estimate, per-crypto Spekulationsfrist countdown, Sparerpauschbetrag usage,
 *  and capital-allocation deployment suggestions. */
export function TaxIntegrationPanels() {
  return (
    <div className="space-y-4">
      <AnnualEstimatePanel />
      <div className="grid gap-4 lg:grid-cols-2">
        <HoldingPeriodPanel />
        <CapitalAllocationPanel />
      </div>
    </div>
  )
}

function AnnualEstimatePanel() {
  const estimate = useAnnualTaxEstimate()
  const [gains, setGains] = useState("")
  const [dividends, setDividends] = useState("")
  const [church, setChurch] = useState(false)
  const [result, setResult] = useState<AnnualTaxResponse | null>(null)

  function run() {
    estimate.mutate(
      {
        realized_gains: parseFloat(gains) || 0,
        dividends: parseFloat(dividends) || 0,
        church_tax: church,
      },
      { onSuccess: (r) => setResult(r) },
    )
  }

  return (
    <Panel title="annual tax estimate" meta="abgeltungsteuer + soli" statusDotColor="accent">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-40">
          <div className="label mb-1">realized gains €</div>
          <Input mono type="number" value={gains} onChange={(e) => setGains(e.target.value)} placeholder="0" />
        </div>
        <div className="w-40">
          <div className="label mb-1">dividends €</div>
          <Input mono type="number" value={dividends} onChange={(e) => setDividends(e.target.value)} placeholder="0" />
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm text-text-secondary">
          <input type="checkbox" checked={church} onChange={(e) => setChurch(e.target.checked)} />
          church tax
        </label>
        <Button disabled={estimate.isPending} onClick={run}>
          estimate
        </Button>
      </div>

      <div className="mt-4">
        {estimate.isPending ? (
          <Skeleton className="h-16" />
        ) : result == null ? (
          <p className="text-sm text-text-label">
            enter realized gains + dividends to estimate Abgeltungsteuer (incl. €1,000 Sparerpauschbetrag).
          </p>
        ) : (
          <div className="flex flex-wrap items-end gap-8">
            <div>
              <div className="label mb-0.5">tax owed</div>
              <NumberDisplay value={result.tax_owed} format="currency" emphasized className="text-2xl text-danger" />
            </div>
            <div>
              <div className="label mb-0.5">taxable base</div>
              <NumberDisplay value={result.taxable_base} format="currency" className="text-xl" />
            </div>
            <div>
              <div className="label mb-0.5">effective rate</div>
              <NumberDisplay value={result.effective_rate * 100} format="percent" decimals={2} className="text-xl" />
            </div>
            <div>
              <div className="label mb-0.5">sparerpauschbetrag used</div>
              <span className="font-mono text-xl text-text tabular-nums">
                {formatCurrency(result.sparerpauschbetrag_used)} / {formatCurrency(result.sparerpauschbetrag)}
              </span>
            </div>
          </div>
        )}
      </div>
    </Panel>
  )
}

function HoldingPeriodPanel() {
  const { data, isLoading } = useFinanceHoldings()
  const crypto = (data?.holdings ?? []).filter((h) => h.type === "crypto")

  return (
    <Panel title="crypto holding period" meta="§23 EStG · 12-month Spekulationsfrist" statusDotColor="accent">
      {isLoading ? (
        <Skeleton className="h-32" />
      ) : crypto.length === 0 ? (
        <p className="text-sm text-text-label">no crypto positions</p>
      ) : (
        <ul className="space-y-2">
          {crypto.map((h) => (
            <CryptoRow key={h.ticker} ticker={h.ticker} />
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs text-text-label">
        crypto gains are tax-free after a 12-month hold — the countdown shows days to that date.
      </p>
    </Panel>
  )
}

function CryptoRow({ ticker }: { ticker: string }) {
  const { data, isLoading } = useHoldingPeriod(ticker)
  if (isLoading) return <li><Skeleton className="h-8" /></li>
  if (!data?.available) {
    return (
      <li className="flex items-center justify-between gap-2 border-b border-border/40 pb-1.5 text-sm">
        <span className="font-mono text-accent">{ticker}</span>
        <span className="text-xs text-text-label">{data?.reason ?? "no data"}</span>
      </li>
    )
  }
  return (
    <li className="flex items-center justify-between gap-2 border-b border-border/40 pb-1.5 text-sm">
      <span className="font-mono text-accent">{ticker}</span>
      <span className="flex items-center gap-4">
        {data.is_tax_free ? (
          <span className="font-mono text-xs text-success">tax-free ✓</span>
        ) : (
          <span className="font-mono text-xs text-warning tabular-nums">
            {data.days_to_tax_free}d to tax-free · {data.tax_free_date}
          </span>
        )}
        <span className="font-mono text-xs text-text-secondary tabular-nums">held {data.days_held}d</span>
      </span>
    </li>
  )
}

function CapitalAllocationPanel() {
  const { data, isLoading } = useCapitalAllocation()
  const suggestions = data?.suggestions ?? []

  return (
    <Panel
      title="capital allocation"
      meta={data ? `${formatCurrency(data.cash_deployable)} deployable` : undefined}
      statusDotColor={suggestions.length > 0 ? "accent" : "muted"}
    >
      {isLoading ? (
        <Skeleton className="h-32" />
      ) : suggestions.length === 0 ? (
        <p className="text-sm text-text-label">
          {data && data.cash_deployable <= 0
            ? "no deployable cash detected"
            : "buckets within target — nothing to deploy"}
        </p>
      ) : (
        <ul className="space-y-2 text-sm">
          {suggestions.map((s) => (
            <li key={s.bucket} className="border-b border-border/40 pb-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-text">{s.label}</span>
                <span className="font-mono text-success tabular-nums">
                  +{formatCurrency(s.suggested_deploy_eur)}
                </span>
              </div>
              <p className="mt-0.5 text-xs text-text-label">{s.rationale}</p>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
