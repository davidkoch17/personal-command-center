import { memo, useMemo, useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { FinanceHolding } from "@/hooks/useFinance"
import { cn, formatCurrency, formatNumber } from "@/lib/utils"

type Kind = "text" | "num" | "currency" | "pct" | "ratio"

interface Col {
  label: string
  key: keyof FinanceHolding
  kind: Kind
}

const COLS: Col[] = [
  { label: "position", key: "name", kind: "text" },
  { label: "type", key: "type", kind: "text" },
  { label: "qty", key: "quantity", kind: "num" },
  { label: "avg cost", key: "avg_cost", kind: "currency" },
  { label: "price", key: "current_price", kind: "currency" },
  { label: "market value", key: "market_value", kind: "currency" },
  { label: "unreal. p&l", key: "unrealized_pnl_pct", kind: "pct" },
  { label: "weight", key: "weight", kind: "pct" },
  { label: "sharpe", key: "sharpe", kind: "ratio" },
  { label: "vol", key: "volatility", kind: "pct" },
  { label: "beta", key: "beta", kind: "ratio" },
]

function render(value: FinanceHolding[keyof FinanceHolding], kind: Kind, currency: string) {
  if (kind === "text") return <span className="text-text">{value ?? "—"}</span>
  const num = typeof value === "number" ? value : null
  if (num == null) return <span className="font-mono text-text-label">—</span>
  if (kind === "currency")
    return <span className="font-mono text-text">{formatCurrency(num, currency)}</span>
  if (kind === "num") return <span className="font-mono text-text">{formatNumber(num, 4)}</span>
  if (kind === "ratio")
    return <span className="font-mono text-text tabular-nums">{num.toFixed(2)}</span>
  // pct — value is a fraction (0.14 -> 14.0%); color P&L by sign.
  const color = num > 0 ? "text-success" : num < 0 ? "text-danger" : "text-text"
  return <span className={cn("font-mono tabular-nums", color)}>{`${(num * 100).toFixed(1)}%`}</span>
}

/** Sortable holdings table for the Phase 15a /api/finance/holdings payload. */
export const FinanceHoldingsTable = memo(function FinanceHoldingsTable({
  holdings,
  onRowClick,
}: {
  holdings: FinanceHolding[]
  onRowClick?: (row: FinanceHolding) => void
}) {
  const [sortKey, setSortKey] = useState<keyof FinanceHolding>("market_value")
  const [dir, setDir] = useState<"asc" | "desc">("desc")

  const sorted = useMemo(() => {
    const copy = [...holdings]
    copy.sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (av == null) return 1
      if (bv == null) return -1
      if (typeof av === "number" && typeof bv === "number") return dir === "asc" ? av - bv : bv - av
      return dir === "asc"
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av))
    })
    return copy
  }, [holdings, sortKey, dir])

  function toggleSort(key: keyof FinanceHolding) {
    if (sortKey === key) setDir((d) => (d === "asc" ? "desc" : "asc"))
    else {
      setSortKey(key)
      setDir("desc")
    }
  }

  if (holdings.length === 0) return <p className="text-sm text-text-label">no holdings</p>

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {COLS.map((c) => (
            <TableHead key={c.key}>
              <button
                type="button"
                onClick={() => toggleSort(c.key)}
                className="flex items-center gap-1 hover:text-text"
              >
                {c.label}
                {sortKey === c.key &&
                  (dir === "asc" ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />)}
              </button>
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((row) => (
          <TableRow
            key={row.ticker}
            className={onRowClick ? "cursor-pointer" : undefined}
            onClick={onRowClick ? () => onRowClick(row) : undefined}
          >
            {COLS.map((c) => (
              <TableCell key={c.key}>{render(row[c.key], c.kind, row.currency)}</TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
})
