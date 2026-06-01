import { useEffect, useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { NumberDisplay } from "@/components/ui/number-display"
import { TradingView } from "@/components/finance/tradingview"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { HoldingRow } from "@/hooks/useFinance"
import { useWatchlistDossier, useAddHypothesis } from "@/hooks/useFinance"
import { useRunSkill } from "@/hooks/useSkills"
import { toast } from "@/lib/toast-store"

/** Find the first row key containing `match` and return its value. */
function pick(row: HoldingRow, match: string): string | number | null {
  const key = Object.keys(row).find((k) => k.includes(match))
  return key ? row[key] : null
}

export function HoldingSubview({
  holding,
  onBack,
}: {
  holding: HoldingRow
  onBack: () => void
}) {
  const ticker = String(pick(holding, "Ticker") ?? "").toUpperCase()
  const name = String(pick(holding, "Position") ?? ticker)
  const pnl = pick(holding, "% Since Bought")
  const pnlNum = typeof pnl === "number" ? pnl : null

  const dossier = useWatchlistDossier(ticker || undefined)
  const addHyp = useAddHypothesis(ticker || undefined)
  const runSkill = useRunSkill()

  const [note, setNote] = useState("")
  const [hyp, setHyp] = useState("")
  const [valOpen, setValOpen] = useState(false)

  useEffect(() => {
    setNote(dossier.data?.position_note ?? "")
  }, [dossier.data?.position_note])

  function started(runId?: string) {
    toast.success("started in background — see background runs", runId)
  }

  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={onBack}
        className="font-mono text-xs text-text-secondary hover:text-accent"
      >
        ← back to holdings
      </button>

      {/* Header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">{name}</h2>
          <span className="font-mono text-sm text-text-secondary">{ticker}</span>
        </div>
        <div className="text-right">
          <div className="label mb-0.5">p&l since bought</div>
          <NumberDisplay value={pnlNum} format="percent" signed className="text-xl" />
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          onClick={() =>
            runSkill.mutate(
              { skill: "earnings_reviewer", args: { ticker }, label: `Earnings ${ticker}` },
              { onSuccess: (r) => started(r.run_id), onError: (e) => toast.error("failed", String(e)) },
            )
          }
        >
          run earnings review
        </Button>
        <Button size="sm" variant="secondary" onClick={() => setValOpen(true)}>
          run valuation review
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() =>
            runSkill.mutate(
              { skill: "why_is_x_moving", args: { ticker }, label: `Why ${ticker} moving` },
              { onSuccess: (r) => started(r.run_id), onError: (e) => toast.error("failed", String(e)) },
            )
          }
        >
          why is this moving?
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Research notes (local) */}
        <Panel title="research notes" statusDotColor="muted">
          <Textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="accumulating notes for this name..."
            rows={5}
          />
          <p className="mt-1 text-xs text-text-label">
            per-holding note persistence pending (backend phase)
          </p>
        </Panel>

        {/* Hypotheses */}
        <Panel
          title="hypotheses"
          meta={`${dossier.data?.hypotheses.length ?? 0}`}
          statusDotColor="accent"
        >
          {dossier.isLoading ? (
            <Skeleton className="h-16" />
          ) : (dossier.data?.hypotheses.length ?? 0) === 0 ? (
            <p className="text-sm text-text-label">no hypotheses for this name</p>
          ) : (
            <ul className="space-y-1 text-sm text-text-secondary">
              {dossier.data!.hypotheses.slice(0, 8).map((h, i) => (
                <li key={i} className="truncate">
                  {String((h as Record<string, unknown>).text ?? JSON.stringify(h))}
                </li>
              ))}
            </ul>
          )}
          <div className="mt-2 flex gap-2">
            <Input
              value={hyp}
              onChange={(e) => setHyp(e.target.value)}
              placeholder="add a hypothesis..."
            />
            <Button
              size="md"
              disabled={!hyp.trim() || addHyp.isPending || !ticker}
              onClick={() =>
                addHyp.mutate(
                  { hypothesis: hyp.trim() },
                  {
                    onSuccess: () => {
                      setHyp("")
                      toast.success("hypothesis added", ticker)
                    },
                    onError: (e) => toast.error("could not add", String(e)),
                  },
                )
              }
            >
              add
            </Button>
          </div>
        </Panel>

        {/* News */}
        <Panel title="news" meta={`${dossier.data?.news.length ?? 0}`} statusDotColor="muted">
          {dossier.isLoading ? (
            <Skeleton className="h-16" />
          ) : (dossier.data?.news.length ?? 0) === 0 ? (
            <p className="text-sm text-text-label">no recent news</p>
          ) : (
            <ul className="space-y-1.5 text-sm">
              {dossier.data!.news.slice(0, 10).map((n, i) => (
                <NewsRow key={i} item={n as Record<string, unknown>} />
              ))}
            </ul>
          )}
        </Panel>

        {/* Filings */}
        <Panel title="filings" meta={`${dossier.data?.filings.length ?? 0}`} statusDotColor="muted">
          {dossier.isLoading ? (
            <Skeleton className="h-16" />
          ) : (dossier.data?.filings.length ?? 0) === 0 ? (
            <p className="text-sm text-text-label">no recent filings</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {dossier.data!.filings.slice(0, 8).map((f, i) => (
                <FilingRow key={i} item={f as Record<string, unknown>} />
              ))}
            </ul>
          )}
        </Panel>
      </div>

      {/* TradingView */}
      <Panel title="chart" statusDotColor="accent">
        {ticker ? (
          <TradingView symbol={ticker} />
        ) : (
          <p className="text-sm text-text-label">no ticker to chart</p>
        )}
      </Panel>

      <ValuationDialog
        open={valOpen}
        onOpenChange={setValOpen}
        ticker={ticker}
        onSubmit={(summary, peers) =>
          runSkill.mutate(
            {
              skill: "valuation_reviewer",
              args: { ticker, your_valuation_summary: summary, peers },
              label: `Valuation ${ticker}`,
            },
            { onSuccess: (r) => started(r.run_id), onError: (e) => toast.error("failed", String(e)) },
          )
        }
      />
    </div>
  )
}

function NewsRow({ item }: { item: Record<string, unknown> }) {
  const title = String(item.title ?? item.headline ?? "untitled")
  const url = item.url ?? item.link
  return (
    <li>
      {typeof url === "string" ? (
        <a href={url} target="_blank" rel="noopener noreferrer" className="text-text hover:text-accent">
          {title}
        </a>
      ) : (
        <span className="text-text">{title}</span>
      )}
    </li>
  )
}

function FilingRow({ item }: { item: Record<string, unknown> }) {
  const form = String(item.form ?? item.type ?? "filing")
  const url = item.url ?? item.link
  const date = String(item.date ?? item.filed ?? "")
  return (
    <li className="flex items-center justify-between gap-2">
      {typeof url === "string" ? (
        <a href={url} target="_blank" rel="noopener noreferrer" className="font-mono text-xs text-text hover:text-accent">
          {form}
        </a>
      ) : (
        <span className="font-mono text-xs text-text">{form}</span>
      )}
      <span className="font-mono text-xs text-text-label">{date.slice(0, 10)}</span>
    </li>
  )
}

function ValuationDialog({
  open,
  onOpenChange,
  ticker,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  ticker: string
  onSubmit: (summary: string, peers: string) => void
}) {
  const [summary, setSummary] = useState("")
  const [peers, setPeers] = useState("")
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>valuation review — {ticker.toLowerCase()}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <div className="label mb-1">your valuation summary</div>
            <Textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              placeholder="your thesis / target / method..."
              rows={4}
            />
          </div>
          <div>
            <div className="label mb-1">peers (comma-separated)</div>
            <Input value={peers} onChange={(e) => setPeers(e.target.value)} mono placeholder="e.g. AAPL, MSFT" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            cancel
          </Button>
          <Button
            disabled={!summary.trim() || !peers.trim()}
            onClick={() => {
              onSubmit(summary.trim(), peers.trim())
              onOpenChange(false)
              setSummary("")
              setPeers("")
            }}
          >
            run
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
