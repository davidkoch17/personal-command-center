import { useEffect, useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { NumberDisplay } from "@/components/ui/number-display"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useDebounce } from "@/hooks/useDebounce"
import {
  useMarketShock,
  useFxShock,
  useWhatIf,
  type MarketShockResponse,
  type FxShockResponse,
  type WhatIfResponse,
} from "@/hooks/useFinance"
import { formatCurrency, isoDate } from "@/lib/utils"

/** Real scenario tools — market shock, what-if counterfactual, FX shock. */
export function ScenarioTools() {
  return (
    <div className="space-y-4">
      <MarketShockPanel />
      <div className="grid gap-4 lg:grid-cols-2">
        <WhatIfPanel />
        <FxShockPanel />
      </div>
    </div>
  )
}

function MarketShockPanel() {
  const [shock, setShock] = useState(-20) // percent
  const debounced = useDebounce(shock, 250)
  const mutation = useMarketShock()
  const [result, setResult] = useState<MarketShockResponse | null>(null)

  const { mutate } = mutation
  useEffect(() => {
    mutate(debounced / 100, { onSuccess: (r) => setResult(r) })
  }, [debounced, mutate])

  const positions = result
    ? Object.entries(result.per_position).filter(([, v]) => v.impact != null)
    : []

  return (
    <Panel
      title="market shock"
      meta={`broad market ${shock > 0 ? "+" : ""}${shock}%`}
      statusDotColor={shock < 0 ? "danger" : "success"}
    >
      <input
        type="range"
        min={-50}
        max={20}
        step={1}
        value={shock}
        onChange={(e) => setShock(Number(e.target.value))}
        className="w-full accent-accent"
      />
      <div className="flex justify-between font-mono text-[10px] text-text-label">
        <span>−50%</span>
        <span>0%</span>
        <span>+20%</span>
      </div>

      <div className="mt-3">
        {mutation.isPending && !result ? (
          <Skeleton className="h-16" />
        ) : result ? (
          <>
            <div className="flex flex-wrap items-end gap-8">
              <div>
                <div className="label mb-0.5">estimated impact</div>
                <NumberDisplay
                  value={result.total_estimated_impact}
                  format="currency"
                  signed
                  emphasized
                  className="text-2xl"
                />
              </div>
              <div>
                <div className="label mb-0.5">% of portfolio</div>
                <NumberDisplay
                  value={result.impact_pct != null ? result.impact_pct * 100 : null}
                  format="percent"
                  signed
                  className="text-2xl"
                />
              </div>
              <div>
                <div className="label mb-0.5">portfolio value</div>
                <span className="font-mono text-lg text-text-secondary">{formatCurrency(result.total_value)}</span>
              </div>
            </div>

            {positions.length > 0 && (
              <table className="mt-4 w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-text-label">
                    <th className="py-1 pr-2 font-normal">ticker</th>
                    <th className="py-1 px-2 text-right font-normal">beta</th>
                    <th className="py-1 px-2 text-right font-normal">value</th>
                    <th className="py-1 px-2 text-right font-normal">impact</th>
                  </tr>
                </thead>
                <tbody className="font-mono tabular-nums">
                  {positions.map(([ticker, v]) => (
                    <tr key={ticker} className="border-b border-border/40">
                      <td className="py-1 pr-2 font-sans text-text">{ticker}</td>
                      <td className="py-1 px-2 text-right text-text-secondary">{v.beta?.toFixed(2) ?? "—"}</td>
                      <td className="py-1 px-2 text-right text-text-secondary">{formatCurrency(v.value)}</td>
                      <td className={`py-1 px-2 text-right ${(v.impact ?? 0) < 0 ? "text-danger" : "text-success"}`}>
                        {formatCurrency(v.impact)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="mt-2 text-xs text-text-label">
              per-position impact = market value × beta (vs s&amp;p 500) × shock.
            </p>
          </>
        ) : (
          <p className="text-sm text-text-label">move the slider to model a market move</p>
        )}
      </div>
    </Panel>
  )
}

function WhatIfPanel() {
  const [ticker, setTicker] = useState("")
  const [qty, setQty] = useState("")
  const [date, setDate] = useState("2024-01-02")
  const mutation = useWhatIf()
  const [result, setResult] = useState<WhatIfResponse | null>(null)

  function run() {
    const t = ticker.trim().toUpperCase()
    const q = Number(qty)
    if (!t || !q || !date) return
    mutation.mutate(
      { ticker: t, action: "hold", qty: q, date },
      { onSuccess: (r) => setResult(r) },
    )
  }

  return (
    <Panel title="what-if" meta="counterfactual p&l" statusDotColor="accent">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="label mb-1">ticker</div>
          <Input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="e.g. GOOGL" mono />
        </div>
        <div>
          <div className="label mb-1">quantity</div>
          <Input type="number" value={qty} onChange={(e) => setQty(e.target.value)} placeholder="e.g. 10" mono />
        </div>
        <div className="col-span-2">
          <div className="label mb-1">as if bought on</div>
          <Input type="date" value={date} max={isoDate()} onChange={(e) => setDate(e.target.value)} mono />
        </div>
      </div>
      <div className="mt-3 flex justify-end">
        <Button onClick={run} disabled={!ticker.trim() || !qty || mutation.isPending}>
          {mutation.isPending ? "computing…" : "compute"}
        </Button>
      </div>

      {result && (
        <div className="mt-3 border-t border-border pt-3">
          {result.error ? (
            <p className="text-sm text-text-label">no data for that ticker / date</p>
          ) : (
            <div className="flex flex-wrap items-end gap-6">
              <div>
                <div className="label mb-0.5">counterfactual p&l</div>
                <NumberDisplay value={result.counterfactual_pnl} format="currency" signed emphasized className="text-xl" />
              </div>
              <div>
                <div className="label mb-0.5">cumulative return</div>
                <NumberDisplay value={result.cumulative_return_pct} format="percent" signed className="text-xl" />
              </div>
              <div className="font-mono text-xs text-text-secondary">
                {formatCurrency(result.initial_price)} → {formatCurrency(result.current_price)}
              </div>
            </div>
          )}
        </div>
      )}
    </Panel>
  )
}

const CURRENCIES = ["USD", "EUR", "GBP"]

function FxShockPanel() {
  const [currency, setCurrency] = useState("USD")
  const [shock, setShock] = useState(-10) // percent
  const debounced = useDebounce(shock, 250)
  const mutation = useFxShock()
  const [result, setResult] = useState<FxShockResponse | null>(null)

  const { mutate } = mutation
  useEffect(() => {
    mutate({ currency, shock_pct: debounced / 100 }, { onSuccess: (r) => setResult(r) })
  }, [currency, debounced, mutate])

  return (
    <Panel title="fx shock" meta={`${currency} ${shock > 0 ? "+" : ""}${shock}%`} statusDotColor="warning">
      <div className="mb-3 w-32">
        <Select value={currency} onValueChange={setCurrency}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CURRENCIES.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <input
        type="range"
        min={-25}
        max={25}
        step={1}
        value={shock}
        onChange={(e) => setShock(Number(e.target.value))}
        className="w-full accent-accent"
      />
      <div className="flex justify-between font-mono text-[10px] text-text-label">
        <span>−25%</span>
        <span>0%</span>
        <span>+25%</span>
      </div>

      <div className="mt-3">
        {mutation.isPending && !result ? (
          <Skeleton className="h-12" />
        ) : result ? (
          <div className="flex flex-wrap items-end gap-8">
            <div>
              <div className="label mb-0.5">portfolio impact</div>
              <NumberDisplay value={result.total_impact} format="currency" signed emphasized className="text-2xl" />
            </div>
            <div>
              <div className="label mb-0.5">{currency} exposure</div>
              <span className="font-mono text-lg text-text-secondary">{formatCurrency(result.total_exposure)}</span>
            </div>
          </div>
        ) : (
          <p className="text-sm text-text-label">no {currency}-denominated exposure</p>
        )}
        <p className="mt-2 text-xs text-text-label">
          impact = market value of {currency} positions × move. position currency from metadata.
        </p>
      </div>
    </Panel>
  )
}
