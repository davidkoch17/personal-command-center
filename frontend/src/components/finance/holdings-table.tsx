import { useMemo, useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { HoldingRow } from "@/hooks/useFinance"
import { formatCurrency, formatNumber, formatPercent, cn } from "@/lib/utils"

type ColKind = "text" | "num" | "currency" | "pct"

interface ColDef {
  label: string
  /** Substring matched against raw DataFrame keys (handles € / spaces). */
  match: string
  kind: ColKind
}

const COLUMNS: ColDef[] = [
  { label: "position", match: "Position", kind: "text" },
  { label: "type", match: "Type", kind: "text" },
  { label: "quantity", match: "Quantity", kind: "num" },
  { label: "avg cost", match: "Avg Cost", kind: "currency" },
  { label: "current price", match: "Current Price", kind: "currency" },
  { label: "market value", match: "Market Value", kind: "currency" },
  { label: "% since bought", match: "% Since Bought", kind: "pct" },
  { label: "% ytd", match: "% YTD", kind: "pct" },
  { label: "% last week", match: "% Last Week", kind: "pct" },
]

/** Find the actual row key whose name contains `match` (first hit). */
function keyFor(row: HoldingRow | undefined, match: string): string | undefined {
  if (!row) return undefined
  return Object.keys(row).find((k) => k.includes(match))
}

function renderCell(value: string | number | null, kind: ColKind) {
  if (kind === "text") return <span className="text-text">{value ?? "—"}</span>
  const num = typeof value === "number" ? value : null
  if (kind === "currency")
    return <span className="font-mono text-text">{formatCurrency(num)}</span>
  if (kind === "num")
    return <span className="font-mono text-text">{formatNumber(num, 2)}</span>
  // pct — color by sign
  const color =
    num == null ? "text-text" : num > 0 ? "text-success" : num < 0 ? "text-danger" : "text-text"
  return <span className={cn("font-mono", color)}>{formatPercent(num)}</span>
}

interface HoldingsTableProps {
  holdings: HoldingRow[]
  onRowClick?: (row: HoldingRow) => void
}

/** Sortable holdings table. Numbers monospace; position name in sans. */
export function HoldingsTable({ holdings, onRowClick }: HoldingsTableProps) {
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [dir, setDir] = useState<"asc" | "desc">("desc")

  const cols = useMemo(
    () =>
      COLUMNS.map((c) => ({ ...c, key: keyFor(holdings[0], c.match) })).filter(
        (c) => c.key,
      ),
    [holdings],
  )

  const sorted = useMemo(() => {
    if (!sortKey) return holdings
    const copy = [...holdings]
    copy.sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (av == null) return 1
      if (bv == null) return -1
      if (typeof av === "number" && typeof bv === "number")
        return dir === "asc" ? av - bv : bv - av
      return dir === "asc"
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av))
    })
    return copy
  }, [holdings, sortKey, dir])

  function toggleSort(key: string) {
    if (sortKey === key) {
      setDir((d) => (d === "asc" ? "desc" : "asc"))
    } else {
      setSortKey(key)
      setDir("desc")
    }
  }

  if (holdings.length === 0)
    return <p className="text-sm text-text-label">no holdings</p>

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {cols.map((c) => (
            <TableHead key={c.key}>
              <button
                type="button"
                onClick={() => toggleSort(c.key!)}
                className="flex items-center gap-1 hover:text-text"
              >
                {c.label}
                {sortKey === c.key &&
                  (dir === "asc" ? (
                    <ChevronUp className="h-3 w-3" />
                  ) : (
                    <ChevronDown className="h-3 w-3" />
                  ))}
              </button>
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((row, i) => (
          <TableRow
            key={i}
            className={onRowClick ? "cursor-pointer" : undefined}
            onClick={onRowClick ? () => onRowClick(row) : undefined}
          >
            {cols.map((c) => (
              <TableCell key={c.key}>{renderCell(row[c.key!], c.kind)}</TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
