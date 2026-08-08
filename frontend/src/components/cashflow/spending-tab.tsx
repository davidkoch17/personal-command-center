import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { Tag } from "@/components/ui/tag"
import { NumberDisplay } from "@/components/ui/number-display"
import { Collapsible } from "@/components/ui/collapsible"
import {
  useCashflowMonths,
  useCashflowSpending,
  type CashflowMerchant,
  type CashflowRecurringItem,
  type CashflowSpendingCategory,
  type CashflowSpendingMover,
} from "@/hooks/useCashflow"
import { MonthPicker } from "./month-picker"
import { cn, formatCurrency, formatPercent } from "@/lib/utils"

// One accent hue family (blue/sky tints) — no categorical "rainbow", matches
// the overview tab's CAT_COLOR convention.
const CAT_COLOR: Record<string, string> = {
  Rent: "bg-blue-600",
  Shopping: "bg-blue-800",
  Restaurants: "bg-sky-400",
  Dining: "bg-sky-400",
  Transport: "bg-blue-500",
  Travel: "bg-sky-500",
  Entertainment: "bg-sky-700",
  Groceries: "bg-blue-400",
  Subscriptions: "bg-blue-300",
  Utilities: "bg-sky-300",
  Health: "bg-sky-600",
}

const CADENCE_LABEL: Record<CashflowRecurringItem["cadence"], string> = {
  weekly: "weekly",
  monthly: "monthly",
  quarterly: "quarterly",
  yearly: "yearly",
}

export function SpendingTab() {
  const monthsQ = useCashflowMonths()
  const months = monthsQ.data?.months ?? []
  const [selected, setSelected] = useState<string | null>(null)
  const month = selected ?? (months.length ? months[months.length - 1] : null)

  const spending = useCashflowSpending(month)

  return (
    <div className="space-y-4">
      <MonthPicker months={months} month={month} onChange={setSelected} />

      {monthsQ.isLoading || spending.isLoading ? (
        <Skeleton className="h-96" />
      ) : !spending.data || !month ? (
        <Panel title="spending" statusDotColor="muted">
          <EmptyState message="no expense data yet." />
        </Panel>
      ) : (
        <>
          <FixedVsVariablePanel data={spending.data.fixed_vs_variable} />
          <RecurringPanel data={spending.data.recurring} />
          <CategoriesPanel categories={spending.data.categories} />
          <BiggestMoversPanel movers={spending.data.biggest_movers} />
        </>
      )}
    </div>
  )
}

// --- Fixed vs variable -----------------------------------------------------

function FixedVsVariablePanel({
  data,
}: {
  data: { fixed: number; variable: number; fixed_share: number | null }
}) {
  const pct = data.fixed_share != null ? Math.round(data.fixed_share * 100) : null
  return (
    <Panel title="fixed vs variable" statusDotColor="accent">
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-sm border border-border bg-bg-panel px-3 py-2">
          <div className="label mb-1">fixed</div>
          <NumberDisplay value={data.fixed} format="currency" emphasized className="text-lg" />
        </div>
        <div className="rounded-sm border border-border bg-bg-panel px-3 py-2">
          <div className="label mb-1">variable</div>
          <NumberDisplay value={data.variable} format="currency" emphasized className="text-lg" />
        </div>
      </div>
      {pct != null && (
        <div className="mt-3 space-y-1.5">
          <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-border">
            <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
            <div className="h-full bg-text-label/40" style={{ width: `${100 - pct}%` }} />
          </div>
          <p className="text-xs text-text-label">{pct}% of spend is fixed / committed</p>
        </div>
      )}
    </Panel>
  )
}

// --- Recurring & subscriptions ----------------------------------------------

function RecurringPanel({ data }: { data: { items: CashflowRecurringItem[]; committed_monthly_total: number } }) {
  return (
    <Panel
      title="recurring & subscriptions"
      meta={`${formatCurrency(data.committed_monthly_total)}/mo committed`}
      statusDotColor={data.items.length ? "accent" : "muted"}
    >
      {data.items.length === 0 ? (
        <EmptyState message="no recurring charges detected yet — needs a consistent cadence across a few months." />
      ) : (
        <div className="space-y-1.5">
          {data.items.map((item) => (
            <div key={item.merchant} className="flex items-center gap-2 text-xs">
              <span className="w-40 shrink-0 truncate text-text-secondary">{item.merchant}</span>
              <Tag variant="muted" className="shrink-0 normal-case">
                {CADENCE_LABEL[item.cadence]}
              </Tag>
              <span className="w-24 shrink-0 truncate text-text-label">{item.category}</span>
              <span className="flex-1 text-right font-mono tabular-nums text-text-secondary">
                {formatCurrency(item.amount)}
              </span>
              {item.price_creep && (
                <Tag variant="warning" className="shrink-0 normal-case">
                  ↑ price creep {item.price_creep_delta != null ? formatCurrency(item.price_creep_delta) : ""}
                </Tag>
              )}
              <span className="w-20 shrink-0 text-right text-text-label">since {item.last_seen}</span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  )
}

// --- Category bars with merchant drill-down ---------------------------------

function MerchantRow({ merchant }: { merchant: CashflowMerchant }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="truncate text-text-secondary">{merchant.merchant}</span>
      <span className="shrink-0 font-mono tabular-nums text-text-label">{formatCurrency(merchant.amount)}</span>
    </div>
  )
}

function CategoryRow({ cat, max }: { cat: CashflowSpendingCategory; max: number }) {
  const pct = max > 0 ? Math.round((cat.amount / max) * 100) : 0
  const color = CAT_COLOR[cat.category] ?? "bg-text-label"

  return (
    <Collapsible
      title={
        <span className="flex items-center gap-2">
          {cat.category}
          <Tag variant={cat.type === "fixed" ? "accent" : "muted"} className="normal-case">
            {cat.type}
          </Tag>
        </span>
      }
      meta={`${formatCurrency(cat.amount)} · ${cat.merchants.length} merchant${cat.merchants.length === 1 ? "" : "s"}`}
      className="!py-2.5"
    >
      <div className="mb-3 h-1.5 w-full overflow-hidden rounded-full bg-border">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      {cat.merchants.length === 0 ? (
        <EmptyState message="no merchant detail." />
      ) : (
        <div className="space-y-1.5">
          {cat.merchants.map((m) => (
            <MerchantRow key={m.merchant} merchant={m} />
          ))}
        </div>
      )}
    </Collapsible>
  )
}

function CategoriesPanel({ categories }: { categories: CashflowSpendingCategory[] }) {
  const max = categories[0]?.amount ?? 0
  return (
    <Panel title="by category" meta="click a category to see merchants" statusDotColor="accent">
      {categories.length === 0 ? (
        <EmptyState message="no expenses recorded this month." />
      ) : (
        <div className="space-y-2">
          {categories.map((cat) => (
            <CategoryRow key={cat.category} cat={cat} max={max} />
          ))}
        </div>
      )}
    </Panel>
  )
}

// --- Biggest movers ----------------------------------------------------------

function MoverRow({ mover }: { mover: CashflowSpendingMover }) {
  const up = mover.delta_percent >= 0
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-28 shrink-0 truncate text-text-secondary">{mover.category}</span>
      <span className="w-16 shrink-0 text-right font-mono tabular-nums text-text-secondary">
        {formatCurrency(mover.amount)}
      </span>
      <span className="w-16 shrink-0 text-right font-mono tabular-nums text-text-label">
        avg {formatCurrency(mover.avg_3mo)}
      </span>
      <span
        className={cn(
          "flex-1 text-right font-mono tabular-nums",
          up ? "text-danger" : "text-success",
        )}
      >
        {formatPercent(mover.delta_percent, 1)}
      </span>
    </div>
  )
}

function BiggestMoversPanel({ movers }: { movers: CashflowSpendingMover[] }) {
  return (
    <Panel title="biggest movers" meta="vs 3-month average" statusDotColor="accent">
      {movers.length === 0 ? (
        <EmptyState message="needs 3 months of prior history to compare against." />
      ) : (
        <div className="space-y-1.5">
          {movers.map((m) => (
            <MoverRow key={m.category} mover={m} />
          ))}
        </div>
      )}
    </Panel>
  )
}
