import { useEffect, useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Toggle } from "@/components/ui/toggle"
import { Skeleton } from "@/components/ui/skeleton"
import { NumberDisplay } from "@/components/ui/number-display"
import { useFinanceHoldings, type FinanceHolding, type OptPortfolio } from "@/hooks/useFinance"
import {
  useOptimizationConstrained,
  type BoundConstraint,
  type ConstraintSet,
} from "@/hooks/useOptimizationConstrained"
import { useConstraintScenarios } from "@/hooks/useConstraintScenarios"
import { useBenchmark } from "@/hooks/useBenchmark"
import { useRiskFreeRate } from "@/hooks/useRiskFreeRate"
import { toast } from "@/lib/toast-store"
import { cn } from "@/lib/utils"

const BUCKET_DEFAULTS: Record<string, { min: number; max: number; label: string }> = {
  etf_foundation: { min: 0.45, max: 0.53, label: "ETF Foundation" },
  single_stocks: { min: 0.17, max: 0.25, label: "Single Stocks" },
  crypto: { min: 0.20, max: 0.28, label: "Crypto" },
  wild_cards: { min: 0.02, max: 0.10, label: "Wild Cards" },
}
const BUCKET_KEYS = Object.keys(BUCKET_DEFAULTS)

interface Section<T> {
  enabled: boolean
  value: T
}

type BoundsMap = Record<string, { min: number; max: number }>

interface ModalState {
  bucketCaps: Section<BoundsMap>
  positionBounds: Section<BoundsMap>
  concentration: Section<{ max_single: number; max_top5: number }>
  hhi: Section<number>
  currency: Section<{ USD: number; EUR: number }>
  volBudget: Section<number>
}

function defaultBucketCaps(): BoundsMap {
  const m: BoundsMap = {}
  for (const [k, d] of Object.entries(BUCKET_DEFAULTS)) m[k] = { min: d.min, max: d.max }
  return m
}

function defaultPositionBounds(holdings: FinanceHolding[]): BoundsMap {
  const m: BoundsMap = {}
  for (const h of holdings) m[h.ticker] = { min: 0, max: 1 }
  return m
}

function defaultState(holdings: FinanceHolding[], currentVol: number | null): ModalState {
  return {
    bucketCaps: { enabled: false, value: defaultBucketCaps() },
    positionBounds: { enabled: false, value: defaultPositionBounds(holdings) },
    concentration: { enabled: false, value: { max_single: 0.10, max_top5: 0.50 } },
    hhi: { enabled: false, value: 0.3 },
    currency: { enabled: false, value: { USD: 0.60, EUR: 0.40 } },
    volBudget: { enabled: false, value: currentVol != null ? Math.round(currentVol * 1000) / 1000 : 0.15 },
  }
}

function buildRequest(state: ModalState): ConstraintSet {
  return {
    bucket_caps: state.bucketCaps.enabled
      ? Object.fromEntries(Object.entries(state.bucketCaps.value).map(([k, v]) => [k, v as BoundConstraint]))
      : null,
    position_bounds: state.positionBounds.enabled
      ? Object.fromEntries(Object.entries(state.positionBounds.value).map(([k, v]) => [k, v as BoundConstraint]))
      : null,
    concentration: state.concentration.enabled || state.hhi.enabled
      ? {
          max_single: state.concentration.enabled ? state.concentration.value.max_single : null,
          max_top5: state.concentration.enabled ? state.concentration.value.max_top5 : null,
          hhi_cap: state.hhi.enabled ? state.hhi.value : null,
        }
      : null,
    currency_caps: state.currency.enabled ? { USD: state.currency.value.USD, EUR: state.currency.value.EUR } : null,
    vol_budget: state.volBudget.enabled ? { max_vol: state.volBudget.value } : null,
  }
}

function num(v: number, d = 2): string {
  return `${(v * 100).toFixed(d)}%`
}

export function ConstraintsModal({
  open,
  onOpenChange,
  currentVol,
  unconstrainedTangency,
  onPreview,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Current portfolio annualized vol (frontier.current?.risk) — vol-budget default. */
  currentVol: number | null
  /** The tab's already-loaded unconstrained tangency (useOptFrontier) — the
   *  delta panel compares the constrained preview against this, no refetch. */
  unconstrainedTangency: OptPortfolio | null
  /** Fired with the constrained result (or null to clear) so the parent chart can overlay it. */
  onPreview: (result: import("@/hooks/useOptimizationConstrained").ConstrainedFrontierResult | null) => void
}) {
  const holdings = useFinanceHoldings()
  const rows = holdings.data?.holdings ?? []
  const [state, setState] = useState<ModalState>(() => defaultState(rows, currentVol))
  const [scenarioName, setScenarioName] = useState("")
  const preview = useOptimizationConstrained()
  const { scenarios, saveScenario } = useConstraintScenarios()
  const [benchmark] = useBenchmark()
  const [rfr] = useRiskFreeRate()

  // The preview was solved against the previous benchmark's expected returns.
  useEffect(() => {
    preview.reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [benchmark, rfr])

  function resetAll() {
    setState(defaultState(rows, currentVol))
    preview.reset()
    onPreview(null)
  }

  function loadScenario(name: string) {
    const s = scenarios.find((sc) => sc.name === name)
    if (!s) return
    const c = s.constraints
    setState({
      bucketCaps: { enabled: !!c.bucket_caps, value: (c.bucket_caps as BoundsMap) ?? defaultBucketCaps() },
      positionBounds: { enabled: !!c.position_bounds, value: (c.position_bounds as BoundsMap) ?? defaultPositionBounds(rows) },
      concentration: {
        enabled: !!c.concentration && (c.concentration.max_single != null || c.concentration.max_top5 != null),
        value: {
          max_single: c.concentration?.max_single ?? 0.10,
          max_top5: c.concentration?.max_top5 ?? 0.50,
        },
      },
      hhi: { enabled: !!c.concentration?.hhi_cap, value: c.concentration?.hhi_cap ?? 0.3 },
      currency: { enabled: !!c.currency_caps, value: { USD: c.currency_caps?.USD ?? 0.6, EUR: c.currency_caps?.EUR ?? 0.4 } },
      volBudget: { enabled: !!c.vol_budget, value: c.vol_budget?.max_vol ?? 0.15 },
    })
    toast.success("scenario loaded", name)
  }

  function runPreview() {
    const req = buildRequest(state)
    preview.mutate(req, {
      onSuccess: (r) => onPreview(r.constrained),
      onError: (e) => toast.error("preview failed", String(e)),
    })
  }

  function saveAsScenario() {
    if (!scenarioName.trim()) return
    saveScenario(scenarioName, buildRequest(state))
    toast.success("scenario saved", scenarioName)
    setScenarioName("")
  }

  const result = preview.data?.constrained

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>constraint explorer</DialogTitle>
        </DialogHeader>

        {scenarios.length > 0 && (
          <div className="mb-4 flex flex-wrap items-center gap-1.5">
            <span className="label">saved scenarios</span>
            {scenarios.map((s) => (
              <button
                key={s.name}
                type="button"
                onClick={() => loadScenario(s.name)}
                className="rounded-sm border border-border px-2 py-1 text-xs text-text-secondary hover:border-accent-dim hover:text-text"
              >
                {s.name}
              </button>
            ))}
          </div>
        )}

        {/* Delta panel — appears once a preview has run. */}
        {result && (
          <div className="mb-4 rounded-sm border border-border bg-bg p-3">
            {!result.feasible ? (
              <p className="text-sm text-danger">
                no feasible portfolio under these constraints
                {result.binding_constraint && (
                  <> — relax <span className="font-mono">{result.binding_constraint.replace(/_/g, " ")}</span></>
                )}
                .
              </p>
            ) : (
              <div className="flex flex-wrap gap-6 text-sm">
                <DeltaStat
                  label="tangency sharpe"
                  constrainedV={result.tangency?.performance?.sharpe ?? null}
                  unconstrainedV={unconstrainedTangency?.performance?.sharpe ?? null}
                  fmt={(v) => v.toFixed(2)}
                  delta={(c, u) => `${c - u >= 0 ? "+" : ""}${Math.round((c - u) * 10000)} bps`}
                />
                <DeltaStat
                  label="tangency vol"
                  constrainedV={result.tangency?.performance?.volatility ?? null}
                  unconstrainedV={unconstrainedTangency?.performance?.volatility ?? null}
                  fmt={num}
                  delta={(c, u) => `${c - u >= 0 ? "+" : ""}${((c - u) * 100).toFixed(2)} pp`}
                />
                <DeltaStat
                  label="tangency exp. return"
                  constrainedV={result.tangency?.performance?.expected_return ?? null}
                  unconstrainedV={unconstrainedTangency?.performance?.expected_return ?? null}
                  fmt={num}
                  delta={(c, u) => `${c - u >= 0 ? "+" : ""}${((c - u) * 100).toFixed(2)} pp`}
                />
              </div>
            )}
          </div>
        )}

        {holdings.isLoading ? (
          <Skeleton className="h-64" />
        ) : (
          <div className="space-y-5">
            {/* 1. Bucket caps */}
            <Section
              title="bucket caps"
              enabled={state.bucketCaps.enabled}
              onToggle={(v) => setState((s) => ({ ...s, bucketCaps: { ...s.bucketCaps, enabled: v } }))}
            >
              <div className="space-y-2">
                {BUCKET_KEYS.map((key) => {
                  const v = state.bucketCaps.value[key]
                  const d = BUCKET_DEFAULTS[key]
                  return (
                    <div key={key} className="flex items-center gap-2">
                      <span className="w-32 text-sm text-text-secondary">{d.label}</span>
                      <BoundInputs
                        bound={v}
                        onChange={(next) =>
                          setState((s) => ({
                            ...s,
                            bucketCaps: { ...s.bucketCaps, value: { ...s.bucketCaps.value, [key]: next } },
                          }))
                        }
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setState((s) => ({
                            ...s,
                            bucketCaps: { ...s.bucketCaps, value: { ...s.bucketCaps.value, [key]: { min: d.min, max: d.max } } },
                          }))
                        }
                        className="text-xs text-text-label hover:text-accent"
                      >
                        reset
                      </button>
                    </div>
                  )
                })}
              </div>
            </Section>

            {/* 2. Per-position weights */}
            <Section
              title="per-position weights"
              enabled={state.positionBounds.enabled}
              onToggle={(v) => setState((s) => ({ ...s, positionBounds: { ...s.positionBounds, enabled: v } }))}
            >
              {rows.length === 0 ? (
                <p className="text-sm text-text-label">no holdings to bound</p>
              ) : (
                <>
                  <FillAll
                    onApply={(min, max) =>
                      setState((s) => {
                        const value: BoundsMap = {}
                        for (const t of Object.keys(s.positionBounds.value)) value[t] = { min, max }
                        return { ...s, positionBounds: { ...s.positionBounds, value } }
                      })
                    }
                  />
                  <div className="mt-2 max-h-48 overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-text-label">
                          <th className="py-1 pr-2 font-normal">ticker</th>
                          <th className="py-1 px-2 text-right font-normal">current weight</th>
                          <th className="py-1 pl-2 font-normal">bounds</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((h) => (
                          <tr key={h.ticker} className="border-t border-border/40">
                            <td className="py-1 pr-2 font-mono text-text">{h.ticker}</td>
                            <td className="py-1 px-2 text-right font-mono text-text-secondary">
                              {h.weight != null ? num(h.weight) : "—"}
                            </td>
                            <td className="py-1 pl-2">
                              <BoundInputs
                                bound={state.positionBounds.value[h.ticker] ?? { min: 0, max: 1 }}
                                onChange={(next) =>
                                  setState((s) => ({
                                    ...s,
                                    positionBounds: {
                                      ...s.positionBounds,
                                      value: { ...s.positionBounds.value, [h.ticker]: next },
                                    },
                                  }))
                                }
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </Section>

            {/* 3. Concentration */}
            <Section
              title="concentration"
              enabled={state.concentration.enabled}
              onToggle={(v) => setState((s) => ({ ...s, concentration: { ...s.concentration, enabled: v } }))}
            >
              <div className="grid grid-cols-2 gap-3 sm:max-w-sm">
                <Field label="max single-position weight (%)">
                  <PctInput
                    value={state.concentration.value.max_single}
                    onChange={(v) =>
                      setState((s) => ({ ...s, concentration: { ...s.concentration, value: { ...s.concentration.value, max_single: v } } }))
                    }
                  />
                </Field>
                <Field label="max top-5 combined (%)">
                  <PctInput
                    value={state.concentration.value.max_top5}
                    onChange={(v) =>
                      setState((s) => ({ ...s, concentration: { ...s.concentration, value: { ...s.concentration.value, max_top5: v } } }))
                    }
                  />
                </Field>
              </div>
              <div className="mt-3 flex items-center gap-3">
                <Toggle
                  value={state.hhi.enabled ? "on" : "off"}
                  options={[{ value: "off", label: "off" }, { value: "on", label: "on" }]}
                  onChange={(v) => setState((s) => ({ ...s, hhi: { ...s.hhi, enabled: v === "on" } }))}
                />
                <span className="text-sm text-text-secondary">HHI cap</span>
                <Input
                  mono type="number" step="0.01" disabled={!state.hhi.enabled}
                  className="w-24"
                  value={state.hhi.value}
                  onChange={(e) => setState((s) => ({ ...s, hhi: { ...s.hhi, value: Number(e.target.value) } }))}
                />
              </div>
            </Section>

            {/* 4. Currency exposure */}
            <Section
              title="currency exposure"
              enabled={state.currency.enabled}
              onToggle={(v) => setState((s) => ({ ...s, currency: { ...s.currency, enabled: v } }))}
            >
              <div className="grid grid-cols-2 gap-3 sm:max-w-sm">
                <Field label="max USD exposure (%)">
                  <PctInput
                    value={state.currency.value.USD}
                    onChange={(v) => setState((s) => ({ ...s, currency: { ...s.currency, value: { ...s.currency.value, USD: v } } }))}
                  />
                </Field>
                <Field label="max EUR exposure (%)">
                  <PctInput
                    value={state.currency.value.EUR}
                    onChange={(v) => setState((s) => ({ ...s, currency: { ...s.currency, value: { ...s.currency.value, EUR: v } } }))}
                  />
                </Field>
              </div>
              <p className="mt-1.5 text-xs text-text-label">
                native currency resolved per ticker (yfinance quote currency), same source the EUR
                conversion layer already uses.
              </p>
            </Section>

            {/* 5. Volatility budget */}
            <Section
              title="volatility budget"
              enabled={state.volBudget.enabled}
              onToggle={(v) => setState((s) => ({ ...s, volBudget: { ...s.volBudget, enabled: v } }))}
            >
              <Field label="max portfolio annualized vol (%)">
                <PctInput
                  className="w-32"
                  value={state.volBudget.value}
                  onChange={(v) => setState((s) => ({ ...s, volBudget: { ...s.volBudget, value: v } }))}
                />
              </Field>
              <p className="mt-1.5 text-xs text-text-label">
                defaults to your current portfolio's annualized vol ({currentVol != null ? num(currentVol) : "—"}).
              </p>
            </Section>

            <p className="text-xs text-text-label">all bound / weight / cap fields are in percent; HHI cap is a 0–1 index.</p>
          </div>
        )}

        <DialogFooter className="mt-5 flex-wrap gap-2">
          <div className="mr-auto flex items-center gap-2">
            <Input
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              placeholder="scenario name…"
              className="h-9 w-40"
            />
            <Button variant="secondary" size="sm" onClick={saveAsScenario} disabled={!scenarioName.trim()}>
              save as scenario
            </Button>
          </div>
          <Button variant="secondary" onClick={resetAll}>
            reset all
          </Button>
          <Button onClick={runPreview} disabled={preview.isPending}>
            {preview.isPending ? "computing…" : "preview"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function Section({
  title,
  enabled,
  onToggle,
  children,
}: {
  title: string
  enabled: boolean
  onToggle: (v: boolean) => void
  children: React.ReactNode
}) {
  return (
    <div className="rounded-sm border border-border p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="label">{title}</span>
        <Toggle
          value={enabled ? "on" : "off"}
          options={[{ value: "off", label: "off" }, { value: "on", label: "on" }]}
          onChange={(v) => onToggle(v === "on")}
        />
      </div>
      <div className={cn(!enabled && "pointer-events-none opacity-40")}>{children}</div>
    </div>
  )
}

/** Percent-entry number field over a fraction-valued state (45 in the box = 0.45 in state). */
function PctInput({
  value,
  onChange,
  className,
  disabled,
}: {
  value: number
  onChange: (fraction: number) => void
  className?: string
  disabled?: boolean
}) {
  return (
    <Input
      mono
      type="number"
      step="1"
      disabled={disabled}
      className={cn("text-right", className)}
      value={Number((value * 100).toFixed(2))}
      onChange={(e) => onChange((Number(e.target.value) || 0) / 100)}
    />
  )
}

function BoundInputs({
  bound,
  onChange,
}: {
  bound: { min: number; max: number }
  onChange: (b: { min: number; max: number }) => void
}) {
  return (
    <span className="flex items-center gap-1.5">
      <PctInput className="h-7 w-20" value={bound.min} onChange={(min) => onChange({ ...bound, min })} />
      <span className="text-text-label">–</span>
      <PctInput className="h-7 w-20" value={bound.max} onChange={(max) => onChange({ ...bound, max })} />
      <span className="text-xs text-text-label">%</span>
    </span>
  )
}

function FillAll({ onApply }: { onApply: (min: number, max: number) => void }) {
  const [min, setMin] = useState("0")
  const [max, setMax] = useState("100")
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-text-label">fill all:</span>
      <Input mono type="number" step="1" className="h-7 w-20" value={min} onChange={(e) => setMin(e.target.value)} />
      <span className="text-text-label">–</span>
      <Input mono type="number" step="1" className="h-7 w-20" value={max} onChange={(e) => setMax(e.target.value)} />
      <Button size="sm" variant="secondary" onClick={() => onApply((Number(min) || 0) / 100, (Number(max) || 100) / 100)}>
        apply to all
      </Button>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="label mb-1">{label}</div>
      {children}
    </div>
  )
}

function DeltaStat({
  label,
  constrainedV,
  unconstrainedV,
  fmt,
  delta,
}: {
  label: string
  constrainedV: number | null
  unconstrainedV: number | null
  fmt: (v: number) => string
  delta: (constrained: number, unconstrained: number) => string
}) {
  return (
    <div>
      <div className="label mb-0.5">{label}</div>
      <div className="font-mono text-text">
        {constrainedV != null ? fmt(constrainedV) : "—"}
        {constrainedV != null && unconstrainedV != null && (
          <span className="ml-1.5 text-xs text-text-label">
            vs {fmt(unconstrainedV)} unconstrained · Δ {delta(constrainedV, unconstrainedV)}
          </span>
        )}
      </div>
    </div>
  )
}
