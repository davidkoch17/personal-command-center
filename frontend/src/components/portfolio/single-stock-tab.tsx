import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { Pencil } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { MetricPanel } from "@/components/finance/metric-panel"
import { PriceSparkline } from "@/components/charts/finance-analytics-charts"
import {
  usePatchPeers,
  usePeers,
  useStockDetail,
  useStockUniverse,
  type PeerRow,
  type StockFundamentals,
  type StockPosition,
} from "@/hooks/usePortfolioHub"
import { useBenchmark } from "@/hooks/useBenchmark"
import { toast } from "@/lib/toast-store"
import { cn, formatCurrency, formatNumber, formatPercent } from "@/lib/utils"

const TIMEFRAMES = [
  { key: "1w", label: "1W" },
  { key: "1m", label: "1M" },
  { key: "3m", label: "3M" },
  { key: "ytd", label: "YTD" },
  { key: "1y", label: "1Y" },
  { key: "all", label: "ALL" },
] as const

const BENCHMARK_LABELS: Record<string, string> = {
  MSCI_WORLD: "MSCI World",
  SPY: "S&P 500",
  DAX: "DAX 40",
  STOXX_600: "STOXX 600",
}

const CCY_SYMBOL: Record<string, string> = { USD: "$", EUR: "€", GBP: "£" }

/** 1.23T / 456.7B / 12.3M — a missing value is "—", never "N/A" or "0". */
function compact(v: number | null | undefined, ccy?: string | null): string {
  if (v == null || Number.isNaN(v)) return "—"
  const abs = Math.abs(v)
  const [div, suffix] = abs >= 1e12 ? [1e12, "T"] : abs >= 1e9 ? [1e9, "B"] : abs >= 1e6 ? [1e6, "M"] : [1, ""]
  const symbol = ccy ? (CCY_SYMBOL[ccy] ?? `${ccy} `) : ""
  return `${symbol}${(v / div).toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}`
}

/** ``signed`` = a change (return, P&L, growth): explicit +/−. Otherwise a level
 *  (margin, yield, weight, range position): plain "16,4 %" with no sign. */
function Pct({ v, decimals = 1, signed = false }: { v: number | null | undefined; decimals?: number; signed?: boolean }) {
  if (v == null || Number.isNaN(v)) return <>—</>
  return <>{signed ? formatPercent(v * 100, decimals).replace("%", " %") : `${formatNumber(v * 100, decimals)} %`}</>
}

/**
 * Single Stock tab (Chunk 4) — pick any held or watchlist ticker and get its
 * header, price chart, fundamentals, your position (if held) and a peer table.
 * One tab, one selector: everything below re-renders off the selection, which
 * lives in the URL (?tab=stock&ticker=ADBE) so it survives reloads and links.
 * A missing yfinance field is "—" throughout.
 */
export function SingleStockTab() {
  const [params, setParams] = useSearchParams()
  const [benchmark] = useBenchmark()
  const [period, setPeriod] = useState<string>("1y")

  const universe = useStockUniverse()
  const held = universe.data?.held ?? []
  const watch = universe.data?.watchlist ?? []

  // URL wins; otherwise default to the first held name (else first watchlist name)
  // without rewriting the URL, so a bare ?tab=stock stays a bare link.
  const fromUrl = params.get("ticker")?.trim().toUpperCase() || null
  const ticker = fromUrl ?? held[0]?.ticker ?? watch[0]?.ticker ?? null

  function select(t: string) {
    setParams((p) => {
      p.set("tab", "stock")
      p.set("ticker", t)
      return p
    })
  }

  const detail = useStockDetail(ticker, period, benchmark)
  const d = detail.data
  const f = d?.fundamentals

  if (universe.isLoading) return <Skeleton className="h-24" />

  const knownTickers = new Set([...held, ...watch].map((e) => e.ticker.toUpperCase()))

  return (
    <div className="space-y-5">
      {/* 1. Selector: held first, then watchlist. */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="label">analyze</span>
        <div className="w-80 max-w-full">
          <Select value={ticker ?? undefined} onValueChange={select} disabled={!ticker && knownTickers.size === 0}>
            <SelectTrigger>
              <SelectValue placeholder="no tickers to analyze" />
            </SelectTrigger>
            <SelectContent>
              {held.length > 0 && (
                <SelectGroup>
                  <SelectLabel>your holdings</SelectLabel>
                  {held.map((e) => (
                    <TickerItem key={e.ticker} ticker={e.ticker} name={e.name} />
                  ))}
                </SelectGroup>
              )}
              {watch.length > 0 && (
                <SelectGroup>
                  <SelectLabel>watchlist</SelectLabel>
                  {watch.map((e) => (
                    <TickerItem key={e.ticker} ticker={e.ticker} name={e.name} />
                  ))}
                </SelectGroup>
              )}
              {/* A ticker opened from a link that is in neither group still needs an item to show. */}
              {ticker && !knownTickers.has(ticker) && <TickerItem ticker={ticker} name="" />}
            </SelectContent>
          </Select>
        </div>
      </div>

      {!ticker ? (
        <Panel title="single stock" statusDotColor="muted">
          <EmptyState message="no tickers to analyze — add positions or watchlist entries first" />
        </Panel>
      ) : (
        <>
          {/* 2. Header */}
          <StockHeader ticker={ticker} f={f} loading={detail.isLoading} />

          {/* 3. Price chart */}
          <Panel
            title="price"
            statusDotColor="invest"
            meta={
              d?.series.change_pct != null ? (
                <span className={cn(d.series.change_pct >= 0 ? "text-success" : "text-danger")}>
                  <Pct v={d.series.change_pct} decimals={2} signed /> · {period}
                </span>
              ) : undefined
            }
          >
            <div className="mb-3 flex flex-wrap gap-1.5">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf.key}
                  type="button"
                  onClick={() => setPeriod(tf.key)}
                  className={cn(
                    "rounded-sm border px-3 py-1 font-mono text-xs transition-colors",
                    period === tf.key
                      ? "border-accent text-accent bg-bg-panel-hover"
                      : "border-border text-text-secondary hover:text-text",
                  )}
                >
                  {tf.label}
                </button>
              ))}
            </div>
            {detail.isLoading ? (
              <Skeleton className="h-60" />
            ) : d && d.series.points.length > 1 ? (
              <PriceSparkline data={d.series.points} currency={f?.currency} />
            ) : (
              <EmptyState message="no price history for this ticker" />
            )}
          </Panel>

          {/* 4. Fundamentals */}
          <Fundamentals f={f} loading={detail.isLoading} benchmarkLabel={BENCHMARK_LABELS[benchmark] ?? benchmark} />

          {/* 5. Your position — only when held. */}
          {d?.position && <PositionCard p={d.position} />}

          {/* 6. Peers */}
          <PeerPanel ticker={ticker} currency={f?.currency} />
        </>
      )}
    </div>
  )
}

function TickerItem({ ticker, name }: { ticker: string; name: string }) {
  return (
    <SelectItem value={ticker}>
      <span className="font-mono">{ticker}</span>
      {name && name !== ticker && <span className="ml-2 text-text-secondary">{name}</span>}
    </SelectItem>
  )
}

function StockHeader({ ticker, f, loading }: { ticker: string; f?: StockFundamentals; loading: boolean }) {
  const delta = f?.day_change_pct
  return (
    <Panel title={ticker} statusDotColor="invest" meta={[f?.exchange, f?.currency].filter(Boolean).join(" · ") || undefined}>
      {loading && !f ? (
        <Skeleton className="h-14" />
      ) : (
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-lg font-medium text-text">{f?.name ?? "—"}</div>
            <div className="text-xs text-text-secondary">
              {[f?.sector, f?.industry].filter(Boolean).join(" · ") || "sector —"}
            </div>
          </div>
          <div className="text-right">
            <div className="font-mono text-2xl font-medium tabular-nums text-invest">
              {f?.price != null ? formatCurrency(f.price, f.currency ?? "USD") : "—"}
            </div>
            <div className={cn("font-mono text-sm tabular-nums", delta == null ? "text-text-label" : delta >= 0 ? "text-success" : "text-danger")}>
              <Pct v={delta} decimals={2} signed /> <span className="text-text-label">today</span>
            </div>
          </div>
        </div>
      )}
    </Panel>
  )
}

function Fundamentals({ f, loading, benchmarkLabel }: { f?: StockFundamentals; loading: boolean; benchmarkLabel: string }) {
  if (loading && !f) return <Skeleton className="h-28" />
  const second = [f?.dividend_yield, f?.week52_position, f?.beta, f?.fcf_yield]
  const showSecondRow = second.some((v) => v != null)
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricPanel label="market cap" dotColor="invest" value={<span className="font-mono tabular-nums">{compact(f?.market_cap, f?.currency)}</span>} />
        <MetricPanel
          label="p/e (forward)"
          dotColor="invest"
          value={<span className="font-mono tabular-nums">{f?.pe_forward != null ? f.pe_forward.toFixed(1) : "—"}</span>}
          caption={f?.pe_trailing != null ? `trailing ${f.pe_trailing.toFixed(1)}` : undefined}
        />
        <MetricPanel
          label="revenue growth (yoy)"
          dotColor="invest"
          value={<span className="font-mono tabular-nums"><Pct v={f?.revenue_growth} signed /></span>}
        />
        <MetricPanel
          label="ebit margin"
          dotColor="invest"
          value={<span className="font-mono tabular-nums"><Pct v={f?.ebit_margin} /></span>}
          caption="operating margin"
        />
      </div>
      {showSecondRow && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricPanel label="dividend yield" dotColor="muted" value={<span className="font-mono tabular-nums"><Pct v={f?.dividend_yield} decimals={2} /></span>} />
          <MetricPanel
            label="52w range position"
            dotColor="muted"
            value={<span className="font-mono tabular-nums"><Pct v={f?.week52_position} decimals={0} /></span>}
            caption={
              f?.week52_low != null && f?.week52_high != null
                ? `${f.week52_low.toLocaleString(undefined, { maximumFractionDigits: 2 })} – ${f.week52_high.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
                : undefined
            }
          />
          <MetricPanel
            label={`beta vs ${benchmarkLabel}`}
            dotColor="muted"
            value={<span className="font-mono tabular-nums">{f?.beta != null ? f.beta.toFixed(2) : "—"}</span>}
            caption="set from the Risk tab's benchmark"
          />
          <MetricPanel label="fcf yield" dotColor="muted" value={<span className="font-mono tabular-nums"><Pct v={f?.fcf_yield} decimals={2} /></span>} />
        </div>
      )}
    </div>
  )
}

function PositionCard({ p }: { p: StockPosition }) {
  const up = (p.pnl ?? 0) >= 0
  return (
    <Panel title="your position" statusDotColor="invest" meta={`${p.quantity.toLocaleString(undefined, { maximumFractionDigits: 6 })} held`}>
      <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2 xl:grid-cols-5">
        <Stat label="cost basis" value={formatCurrency(p.cost_basis)} />
        <Stat label="current value" value={formatCurrency(p.current_value)} />
        <Stat
          label="p&l"
          value={
            <span className={cn(p.pnl == null ? "text-text-label" : up ? "text-success" : "text-danger")}>
              {p.pnl != null ? `${up ? "+" : ""}${formatCurrency(p.pnl)}` : "—"}{" "}
              <span className="text-sm">
                (<Pct v={p.pnl_pct} decimals={1} signed />)
              </span>
            </span>
          }
        />
        <Stat label="weight in portfolio" value={<Pct v={p.weight} decimals={1} />} />
        <Stat label="days held" value={p.days_held != null ? p.days_held.toLocaleString() : "—"} />
      </div>
      {p.fx_stale && <p className="mt-2 text-xs text-warning">EUR conversion used a stale FX rate</p>}
    </Panel>
  )
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="label mb-0.5">{label}</div>
      <div className="font-mono text-lg tabular-nums text-text">{value}</div>
    </div>
  )
}

function PeerPanel({ ticker, currency }: { ticker: string; currency?: string | null }) {
  const peers = usePeers(ticker)
  const patch = usePatchPeers(ticker)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState("")

  // Leaving the ticker abandons any half-typed edit.
  useEffect(() => setEditing(false), [ticker])

  const data = peers.data
  const custom = data?.source === "override"

  function startEdit() {
    setDraft((data?.peers ?? []).filter((r) => !r.is_subject).map((r) => r.ticker).join(", "))
    setEditing(true)
  }

  function save(list: string[]) {
    patch.mutate(list, {
      onSuccess: () => setEditing(false),
      onError: (e) => toast.error("couldn't save peers", String(e)),
    })
  }

  function onSave() {
    save(draft.split(/[\s,;]+/).filter(Boolean))
  }

  return (
    <Panel
      title="peer comparison"
      statusDotColor="invest"
      meta={
        <span className="flex items-center gap-2">
          {data && (
            <span
              className={cn(
                "rounded-sm border px-1 text-[10px] uppercase tracking-wider",
                custom ? "border-invest/30 bg-invest/10 text-invest" : "border-border text-text-label",
              )}
            >
              {custom ? "custom" : "auto"}
            </span>
          )}
          {!editing && (
            <button
              type="button"
              onClick={startEdit}
              aria-label="edit peers"
              title="edit peers"
              className="text-text-label hover:text-text"
              disabled={!data}
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
          )}
        </span>
      }
    >
      {editing && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onSave()}
            placeholder="peer tickers, comma-separated (e.g. MSFT, CRM, ORCL)"
            className="max-w-md"
            autoFocus
          />
          <Button size="sm" onClick={onSave} disabled={patch.isPending}>
            save
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>
            cancel
          </Button>
          {custom && (
            <Button size="sm" variant="secondary" onClick={() => save([])} disabled={patch.isPending}>
              clear override (revert to auto)
            </Button>
          )}
        </div>
      )}

      {peers.isLoading ? (
        <Skeleton className="h-32" />
      ) : !data || data.peers.length <= 1 ? (
        <EmptyState message="no peers found — add some with the pencil" />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ticker</TableHead>
              <TableHead className="text-right">mkt cap</TableHead>
              <TableHead className="text-right">p/e fwd</TableHead>
              <TableHead className="text-right">ytd</TableHead>
              <TableHead className="text-right">1y</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.peers.map((r) => (
              <PeerTableRow key={r.ticker} r={r} currency={r.is_subject ? currency : undefined} />
            ))}
          </TableBody>
        </Table>
      )}
      {data && !custom && data.peers.some((r) => r.in_band === false) && (
        <p className="mt-2 text-xs text-text-label">
          ◦ nearest same-sector name outside the ±50% market-cap band (not enough in-band matches in your universe)
        </p>
      )}
    </Panel>
  )
}

function PeerTableRow({ r, currency }: { r: PeerRow; currency?: string | null }) {
  const ret = (v: number | null) => (
    <span className={cn(v == null ? "text-text-label" : v >= 0 ? "text-success" : "text-danger")}>
      <Pct v={v} decimals={1} signed />
    </span>
  )
  return (
    <TableRow className={cn(r.is_subject && "bg-invest/10")}>
      <TableCell>
        <div className="flex items-baseline gap-2">
          <span className={cn("font-mono", r.is_subject && "font-semibold text-invest")}>{r.ticker}</span>
          {r.in_band === false && <span title="outside the ±50% market-cap band" className="text-text-label">◦</span>}
        </div>
        <div className="max-w-[16rem] truncate text-xs text-text-secondary">{r.name ?? "—"}</div>
      </TableCell>
      <TableCell className="text-right font-mono tabular-nums">{compact(r.market_cap, currency)}</TableCell>
      <TableCell className="text-right font-mono tabular-nums">{r.pe_forward != null ? r.pe_forward.toFixed(1) : "—"}</TableCell>
      <TableCell className="text-right font-mono tabular-nums">{ret(r.ytd_return)}</TableCell>
      <TableCell className="text-right font-mono tabular-nums">{ret(r.return_1y)}</TableCell>
    </TableRow>
  )
}
