import { Collapsible } from "@/components/ui/collapsible"
import {
  HitRatePanel,
  AntiPortfolioPanel,
  DecisionList,
  DecisionLogForm,
} from "@/components/finance/journal-panel"

/**
 * Decision Journal page (/decision-journal) — the full behavioral layer:
 * hypothesis hit rate, anti-portfolio, the filterable decision log, and a
 * log-a-decision form. Each decision is expandable (view) with retrospective
 * editing.
 */
export function DecisionJournal() {
  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="text-3xl font-semibold tracking-tight">decision journal</h1>
        <span className="font-mono text-sm text-text-secondary">behavioral layer · sections 12 · 14 · 15 · 16</span>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <HitRatePanel />
        <AntiPortfolioPanel />
      </div>

      <DecisionList filterable />

      <Collapsible title="log a decision" meta="thesis · conviction · pre-mortem" defaultOpen>
        <DecisionLogForm />
      </Collapsible>
    </div>
  )
}
