import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { NumberDisplay } from "@/components/ui/number-display"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useCashflowMonths, useCashflowSummary, useCashflowTransactions } from "@/hooks/useCashflow"
import { MonthPicker } from "./month-picker"
import { formatCurrency } from "@/lib/utils"

// One accent hue family (blue/sky tints) — no categorical "rainbow".
const CATEGORY_COLORS: Record<string, string> = {
  Rent: "bg-blue-600",
  Groceries: "bg-blue-400",
  Dining: "bg-sky-400",
  Transport: "bg-blue-500",
  Travel: "bg-sky-500",
  Subscriptions: "bg-blue-300",
  Utilities: "bg-sky-300",
  Insurance: "bg-blue-700",
  Health: "bg-sky-600",
  Shopping: "bg-blue-800",
  Entertainment: "bg-sky-700",
  "Taxes & Fees": "bg-blue-200",
  Other: "bg-text-label",
}

export function TransactionsTab() {
  const monthsQ = useCashflowMonths()
  const months = monthsQ.data?.months ?? []
  const [selected, setSelected] = useState<string | null>(null)
  const month = selected ?? (months.length ? months[months.length - 1] : null)
  const [catFilter, setCatFilter] = useState<string>("all")

  const summary = useCashflowSummary(month)
  const txns = useCashflowTransactions(month)

  const totalIncome = summary.data?.income_total ?? 0
  const totalExpenses = summary.data?.expenses_total ?? 0
  const net = summary.data?.net ?? 0

  const filteredTx = (txns.data?.transactions ?? []).filter(
    (t) => catFilter === "all" || t.category === catFilter,
  )

  if (monthsQ.isLoading) return <Skeleton className="h-96" />

  return (
    <div className="space-y-4">
      <MonthPicker
        months={months}
        month={month}
        onChange={(m) => {
          setSelected(m)
          setCatFilter("all")
        }}
      />

      {summary.isLoading ? (
        <Skeleton className="h-64" />
      ) : !summary.data ? (
        <Panel title="transactions" statusDotColor="muted">
          <EmptyState message="no data for this month." />
        </Panel>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Panel title="income" statusDotColor="success" className="!py-3">
              <NumberDisplay value={totalIncome} format="currency" emphasized />
            </Panel>
            <Panel title="expenses" statusDotColor="danger" className="!py-3">
              <NumberDisplay value={totalExpenses} format="currency" emphasized />
            </Panel>
            <Panel title="net" statusDotColor={net >= 0 ? "success" : "danger"} className="!py-3">
              <NumberDisplay value={net} format="currency" emphasized signed />
            </Panel>
            <Panel title="savings rate" statusDotColor="accent" className="!py-3">
              <NumberDisplay
                value={summary.data.savings_rate != null ? summary.data.savings_rate * 100 : null}
                format="percent"
                emphasized
                signed
              />
            </Panel>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="revenue by source" statusDotColor="success">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>source</TableHead>
                    <TableHead className="text-right">amount</TableHead>
                    <TableHead className="text-right">share</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(summary.data.income_by_category)
                    .sort(([, a], [, b]) => b - a)
                    .map(([source, amount]) => (
                      <TableRow key={source}>
                        <TableCell className="text-text">{source}</TableCell>
                        <TableCell className="text-right font-mono">{formatCurrency(amount)}</TableCell>
                        <TableCell className="text-right font-mono text-text-label">
                          {totalIncome ? `${((amount / totalIncome) * 100).toFixed(0)}%` : "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  <TableRow className="border-t border-border font-semibold">
                    <TableCell>total</TableCell>
                    <TableCell className="text-right font-mono">{formatCurrency(totalIncome)}</TableCell>
                    <TableCell />
                  </TableRow>
                </TableBody>
              </Table>
            </Panel>

            <Panel title="expenses by category" statusDotColor="danger">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>category</TableHead>
                    <TableHead className="text-right">amount</TableHead>
                    <TableHead className="text-right">share</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {summary.data.expenses_by_category.map((c) => {
                    const pct = totalExpenses ? (c.amount / totalExpenses) * 100 : 0
                    const color = CATEGORY_COLORS[c.category] ?? CATEGORY_COLORS.Other
                    return (
                      <TableRow
                        key={c.category}
                        className="cursor-pointer hover:bg-bg-panel-hover"
                        onClick={() => setCatFilter((f) => (f === c.category ? "all" : c.category))}
                      >
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className={`h-2 w-2 rounded-full ${color}`} />
                            <span className="text-text">{c.category}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-right font-mono">{formatCurrency(c.amount)}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="h-1.5 w-16 rounded-full bg-border">
                              <div
                                className={`h-full rounded-full ${color}`}
                                style={{ width: `${Math.min(pct, 100)}%` }}
                              />
                            </div>
                            <span className="w-8 text-right font-mono text-xs text-text-label">{pct.toFixed(0)}%</span>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                  <TableRow className="border-t border-border font-semibold">
                    <TableCell>total</TableCell>
                    <TableCell className="text-right font-mono">{formatCurrency(totalExpenses)}</TableCell>
                    <TableCell />
                  </TableRow>
                </TableBody>
              </Table>
              <p className="mt-1 text-xs text-text-label">click a row to filter transactions below</p>
            </Panel>
          </div>

          <Panel
            title={catFilter === "all" ? "all transactions" : `transactions · ${catFilter}`}
            meta={`${filteredTx.length} rows`}
            statusDotColor="muted"
          >
            {catFilter !== "all" && (
              <button onClick={() => setCatFilter("all")} className="mb-2 text-xs text-accent hover:underline">
                ← clear filter
              </button>
            )}
            <div className="max-h-96 overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>date</TableHead>
                    <TableHead>description</TableHead>
                    <TableHead>category</TableHead>
                    <TableHead>account</TableHead>
                    <TableHead className="text-right">amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredTx.map((t, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-mono text-xs text-text-label">{t.date}</TableCell>
                      <TableCell className="max-w-[220px] truncate text-sm">{t.description}</TableCell>
                      <TableCell>
                        <span className="rounded bg-bg-panel-hover px-1.5 py-0.5 text-xs text-text-secondary">
                          {t.category}
                        </span>
                      </TableCell>
                      <TableCell className="text-xs text-text-label">{t.account}</TableCell>
                      <TableCell
                        className={`text-right font-mono text-sm ${t.direction === "income" ? "text-success" : ""}`}
                      >
                        {t.direction === "income" ? "+" : "−"}
                        {formatCurrency(t.amount)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Panel>
        </>
      )}
    </div>
  )
}
