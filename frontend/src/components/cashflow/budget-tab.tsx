import { useEffect, useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { Input } from "@/components/ui/input"
import { NumberDisplay } from "@/components/ui/number-display"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useCashflowBudget, useCashflowMonths, useCashflowSummary, useSetCashflowBudget } from "@/hooks/useCashflow"
import { formatCurrency } from "@/lib/utils"

export function BudgetTab() {
  const monthsQ = useCashflowMonths()
  const months = monthsQ.data?.months ?? []
  const latestMonth = months.length ? months[months.length - 1] : null

  const summary = useCashflowSummary(latestMonth)
  const budget = useCashflowBudget()
  const setBudget = useSetCashflowBudget()

  const [drafts, setDrafts] = useState<Record<string, string>>({})

  // Seed local draft inputs once the saved targets load, without clobbering
  // whatever the user is actively typing.
  useEffect(() => {
    if (!budget.data) return
    setDrafts((prev) => {
      const next = { ...prev }
      for (const [cat, val] of Object.entries(budget.data!.budget)) {
        if (!(cat in next)) next[cat] = String(val)
      }
      return next
    })
  }, [budget.data])

  if (monthsQ.isLoading || summary.isLoading || budget.isLoading) return <Skeleton className="h-64" />

  const actuals = summary.data?.expenses_by_category ?? []
  if (actuals.length === 0) {
    return (
      <Panel title="budget" statusDotColor="muted">
        <p className="text-sm text-text-label">no category data yet.</p>
      </Panel>
    )
  }

  function saveTarget(category: string) {
    const raw = drafts[category] ?? ""
    const num = parseFloat(raw)
    setBudget.mutate({ category, value: Number.isFinite(num) ? num : null })
  }

  return (
    <Panel title="budget vs actual" meta={latestMonth ?? undefined} statusDotColor="accent">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>category</TableHead>
            <TableHead>actual</TableHead>
            <TableHead>target</TableHead>
            <TableHead>variance</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {actuals.map((c) => {
            const draft = drafts[c.category] ?? ""
            const target = parseFloat(draft)
            const variance = Number.isFinite(target) ? target - c.amount : null
            return (
              <TableRow key={c.category}>
                <TableCell className="text-text">{c.category}</TableCell>
                <TableCell className="font-mono">{formatCurrency(c.amount)}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-1.5">
                    <Input
                      mono
                      className="h-7 w-28"
                      value={draft}
                      onChange={(e) => setDrafts((d) => ({ ...d, [c.category]: e.target.value }))}
                      onBlur={() => saveTarget(c.category)}
                      placeholder="—"
                    />
                  </div>
                </TableCell>
                <TableCell>
                  {variance == null ? (
                    <span className="text-text-label">—</span>
                  ) : (
                    <NumberDisplay value={variance} format="currency" signed />
                  )}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      <p className="mt-2 text-xs text-text-label">targets save automatically when you click away from the field.</p>
    </Panel>
  )
}
