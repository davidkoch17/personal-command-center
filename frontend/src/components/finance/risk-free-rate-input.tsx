import { useEffect, useState } from "react"
import { Input } from "@/components/ui/input"
import { InfoTip } from "@/components/ui/info-tip"
import { DEFAULT_RFR, MAX_RFR, useRiskFreeRate } from "@/hooks/useRiskFreeRate"

/**
 * Risk-free rate control (Chunk 8). One number, in percent, that every Sharpe / Sortino / CAPM
 * figure in the app reads (Risk, Holdings, Portfolio KPI band, Optimization, Benchmarks, SML,
 * forward simulator). Stored in localStorage; each dependent query has the rate in its key, so
 * committing a new value refetches exactly those. Blank or out-of-range input is rejected.
 */
export function RiskFreeRateInput() {
  const [rfr, setRfr] = useRiskFreeRate()
  const fmt = (v: number) => String(Number((v * 100).toFixed(3)))
  const [draft, setDraft] = useState(fmt(rfr))

  // Keep the box in step when the rate changes elsewhere (another tab / reset).
  useEffect(() => setDraft(fmt(rfr)), [rfr])

  const parsed = draft.trim() === "" ? NaN : Number(draft) / 100
  const valid = Number.isFinite(parsed) && parsed >= 0 && parsed <= MAX_RFR

  function commit() {
    if (valid) setRfr(parsed)
    else setDraft(fmt(rfr)) // reject: snap back to the last good value
  }

  return (
    <div>
      <div className="mb-1 flex items-center gap-1.5">
        <span className="label">risk-free rate (%)</span>
        <InfoTip text="Annual risk-free rate used in every Sharpe, Sortino and CAPM expected-return calculation across the app (default 4%). Fama-French factor regressions use Ken French's own monthly risk-free series instead." />
      </div>
      <div className="flex items-center gap-2">
        <Input
          mono
          type="number"
          step="0.25"
          min="0"
          max={MAX_RFR * 100}
          className="h-9 w-24 text-right"
          value={draft}
          aria-label="risk-free rate in percent"
          aria-invalid={!valid}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => e.key === "Enter" && commit()}
        />
        {rfr !== DEFAULT_RFR && (
          <button type="button" onClick={() => setRfr(DEFAULT_RFR)} className="text-xs text-text-label hover:text-accent">
            reset to {fmt(DEFAULT_RFR)}%
          </button>
        )}
      </div>
      {!valid && <p className="mt-1 text-xs text-danger">enter a rate between 0 and {MAX_RFR * 100}%</p>}
    </div>
  )
}
