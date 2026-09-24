import { Select, SelectContent, SelectItem, SelectTrigger } from "@/components/ui/select"
import { usePatchPositionBucket, type BucketSource } from "@/hooks/useFinance"
import { cn } from "@/lib/utils"

const BUCKET_LABELS: Record<string, string> = {
  etf_foundation: "ETF Foundation",
  single_stocks: "Single Stocks",
  crypto: "Crypto",
  wild_cards: "Wild Cards",
}
const BUCKET_OPTIONS = Object.entries(BUCKET_LABELS)

// Sentinel item value for "clear override" — distinct from any real bucket key.
const CLEAR = "__clear_override__"

/**
 * Editable bucket cell (Chunk 2.5) — shared by the workspace Holdings table
 * and the Portfolio Hub Holdings tab, so both editing surfaces stay in sync
 * (one PATCH endpoint, one component, no duplicated dropdown logic). Click
 * anywhere in the cell to open the picker; "auto" (grey) marks a value that
 * came from config/ticker_buckets.yaml, "custom" (invest violet) marks a
 * manual override — no badge when unassigned.
 */
export function BucketCell({
  ticker,
  bucket,
  bucketSource,
}: {
  ticker: string
  bucket: string
  bucketSource: BucketSource
}) {
  const patch = usePatchPositionBucket()

  function onChange(value: string) {
    if (value === bucket && value !== CLEAR) return
    patch.mutate({ ticker, bucket: value === CLEAR ? null : value })
  }

  return (
    <Select value={bucket in BUCKET_LABELS ? bucket : undefined} onValueChange={onChange}>
      <SelectTrigger
        className="h-auto w-auto gap-1.5 border-none bg-transparent px-1 py-0.5 text-sm hover:bg-bg-panel-hover focus:border-none"
        disabled={patch.isPending}
      >
        <span className={cn(bucket === "unassigned" ? "text-text-label" : "text-text")}>
          {BUCKET_LABELS[bucket] ?? "unassigned"}
        </span>
        {bucketSource === "map" && (
          <span className="rounded-sm border border-border px-1 text-[10px] uppercase tracking-wider text-text-label">
            auto
          </span>
        )}
        {bucketSource === "override" && (
          <span className="rounded-sm border border-invest/30 bg-invest/10 px-1 text-[10px] uppercase tracking-wider text-invest">
            custom
          </span>
        )}
      </SelectTrigger>
      <SelectContent>
        {BUCKET_OPTIONS.map(([key, label]) => (
          <SelectItem key={key} value={key}>
            {label}
          </SelectItem>
        ))}
        {bucketSource === "override" && (
          <SelectItem value={CLEAR} className="text-text-secondary">
            clear override (revert to auto)
          </SelectItem>
        )}
      </SelectContent>
    </Select>
  )
}
