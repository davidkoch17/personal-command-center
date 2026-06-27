import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Tag } from "@/components/ui/tag"
import { NumberDisplay } from "@/components/ui/number-display"
import { TradingView } from "@/components/finance/tradingview"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useWatchlistDossier, useAddHypothesis } from "@/hooks/useFinance"
import { useRunSkill } from "@/hooks/useSkills"
import { openInOs } from "@/lib/open-in-os"
import { toast } from "@/lib/toast-store"

type Dict = Record<string, unknown>

export function WatchlistTicker() {
  const { ticker: raw } = useParams<{ ticker: string }>()
  const ticker = raw ? decodeURIComponent(raw).toUpperCase() : undefined
  const { data, isLoading, isError } = useWatchlistDossier(ticker)
  const addHyp = useAddHypothesis(ticker)
  const runSkill = useRunSkill()

  const [hyp, setHyp] = useState("")
  const [note, setNote] = useState("")
  const [ask, setAsk] = useState("")
  const [modelOpen, setModelOpen] = useState(false)
  const [valOpen, setValOpen] = useState(false)
  const [peersOpen, setPeersOpen] = useState(false)

  useEffect(() => setNote(data?.position_note ?? ""), [data?.position_note])

  function started(runId?: string) {
    toast.success("started in background — see background runs", runId)
  }
  function run(skill: string, args: Record<string, unknown>, label: string) {
    runSkill.mutate(
      { skill, args, label },
      { onSuccess: (r) => started(r.run_id), onError: (e) => toast.error("failed", String(e)) },
    )
  }

  const price = (data?.price ?? {}) as Dict

  return (
    <div className="min-h-screen bg-bg text-text p-6">
      <div className="mx-auto max-w-[1200px] space-y-5">
        <div className="flex items-center justify-between">
          <Link to="/portfolio?tab=watchlist" className="font-mono text-xs text-text-secondary hover:text-accent">
            ← watchlist
          </Link>
          {ticker && <span className="font-mono text-xs text-text-label">{ticker}</span>}
        </div>

        {isError && (
          <Panel title="error" statusDotColor="danger">
            <p className="text-text-secondary">could not load dossier for {ticker}.</p>
          </Panel>
        )}
        {isLoading && (
          <div className="space-y-4">
            <Skeleton className="h-16" />
            <Skeleton className="h-40" />
          </div>
        )}

        {data && ticker && (
          <>
            {/* Header */}
            <div className="flex items-end justify-between gap-4">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight normal-case">{data.name || ticker}</h1>
                <span className="font-mono text-sm text-text-secondary">{ticker}</span>
              </div>
              <div className="flex gap-5 text-right">
                <div>
                  <div className="label mb-0.5">close</div>
                  <NumberDisplay value={(price.last_close as number) ?? null} format="currency" />
                </div>
                <div>
                  <div className="label mb-0.5">1w</div>
                  <NumberDisplay value={(price.week_change_pct as number) ?? null} format="percent" signed />
                </div>
                <div>
                  <div className="label mb-0.5">1m</div>
                  <NumberDisplay value={(price.month_change_pct as number) ?? null} format="percent" signed />
                </div>
              </div>
            </div>

            {/* Skill action row */}
            <Panel title="skills" statusDotColor="accent">
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={() => run("earnings_reviewer", { ticker }, `Earnings ${ticker}`)}>
                  earnings review
                </Button>
                <Button size="sm" variant="secondary" onClick={() => setValOpen(true)}>
                  valuation review
                </Button>
                <Button size="sm" variant="secondary" onClick={() => setModelOpen(true)}>
                  build model
                </Button>
                <Button size="sm" variant="secondary" onClick={() => setPeersOpen(true)}>
                  compare to peers
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => run("generate_thesis_statement", { ticker, name: data.name ?? "" }, `Thesis ${ticker}`)}
                >
                  generate thesis
                </Button>
              </div>
            </Panel>

            <div className="grid gap-4 lg:grid-cols-2">
              {/* 1. Status + position */}
              <Panel title="status + position" statusDotColor="accent">
                <div className="flex flex-wrap items-center gap-2">
                  <Tag variant="muted">{data.status || "—"}</Tag>
                  <Tag variant="muted">{data.tier || "untagged"}</Tag>
                </div>
                {data.position_note && (
                  <p className="mt-2 text-sm text-text-secondary">{data.position_note}</p>
                )}
              </Panel>

              {/* 2. Active hypotheses */}
              <Panel title="active hypotheses" meta={`${data.hypotheses.length}`} statusDotColor="accent">
                {data.hypotheses.length === 0 ? (
                  <p className="text-sm text-text-label">none for this name</p>
                ) : (
                  <ul className="space-y-1 text-sm text-text-secondary">
                    {data.hypotheses.slice(0, 8).map((h, i) => (
                      <li key={i} className="truncate">
                        {String((h as Dict).text ?? JSON.stringify(h))}
                      </li>
                    ))}
                  </ul>
                )}
                <div className="mt-2 flex gap-2">
                  <Input value={hyp} onChange={(e) => setHyp(e.target.value)} placeholder="add a hypothesis..." />
                  <Button
                    disabled={!hyp.trim() || addHyp.isPending}
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

              {/* 4. News */}
              <Panel title="news feed" meta={`${data.news.length}`} statusDotColor="muted">
                {data.news.length === 0 ? (
                  <p className="text-sm text-text-label">no recent news</p>
                ) : (
                  <ul className="space-y-1.5 text-sm">
                    {data.news.slice(0, 20).map((n, i) => {
                      const o = n as Dict
                      const url = (o.url ?? o.link) as string | undefined
                      const title = String(o.title ?? o.headline ?? "untitled")
                      return (
                        <li key={i}>
                          {url ? (
                            <a href={url} target="_blank" rel="noopener noreferrer" className="text-text hover:text-accent">
                              {title}
                            </a>
                          ) : (
                            <span className="text-text">{title}</span>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                )}
              </Panel>

              {/* 5. Filings + summarize */}
              <Panel title="filings" meta={`${data.filings.length}`} statusDotColor="muted">
                {data.filings.length === 0 ? (
                  <p className="text-sm text-text-label">no recent filings</p>
                ) : (
                  <ul className="space-y-1 text-sm">
                    {data.filings.slice(0, 8).map((f, i) => {
                      const o = f as Dict
                      const url = (o.url ?? o.link) as string | undefined
                      const form = String(o.form ?? o.type ?? "filing")
                      return (
                        <li key={i} className="flex items-center justify-between gap-2">
                          <span className="font-mono text-xs text-text">{form}</span>
                          {url && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => run("summarize_filing", { ticker, filing_url: url }, `Summarize ${form} ${ticker}`)}
                            >
                              summarize
                            </Button>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                )}
              </Panel>

              {/* 7. Recent signals */}
              <Panel title="recent agent signals" meta={`${data.signals.length}`} statusDotColor="muted">
                {data.signals.length === 0 ? (
                  <p className="text-sm text-text-label">no signals in recent briefs</p>
                ) : (
                  <ul className="space-y-1 text-sm text-text-secondary">
                    {data.signals.slice(0, 8).map((s, i) => (
                      <li key={i} className="truncate">
                        {String((s as Dict).text ?? JSON.stringify(s))}
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>

              {/* 8. Research notes */}
              <Panel title="research notes" statusDotColor="muted">
                <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={5} placeholder="accumulating notes..." />
                <p className="mt-1 text-xs text-text-label">note persistence pending (backend phase)</p>
              </Panel>
            </div>

            {/* 3. TradingView */}
            <Panel title="chart" statusDotColor="accent">
              <TradingView symbol={ticker} />
            </Panel>

            {/* 6 / 9 / 10 */}
            <div className="grid gap-4 lg:grid-cols-3">
              <Panel title="comparables" statusDotColor="muted">
                <p className="mb-2 text-sm text-text-label">peer comp table builds via skill.</p>
                <Button size="sm" variant="secondary" onClick={() => setPeersOpen(true)}>
                  compare to peers
                </Button>
              </Panel>
              <Panel title="my model" statusDotColor="muted">
                <p className="mb-2 text-sm text-text-label">link a dcf if built.</p>
                <Button size="sm" variant="secondary" onClick={() => openInOs(`${ticker}_model.xlsx`)}>
                  open in os
                </Button>
              </Panel>
              <Panel title="decision log" statusDotColor="muted">
                <p className="text-sm text-text-label">decision-log filter endpoint pending</p>
              </Panel>
            </div>

            {/* 11. Ask Claude */}
            <Panel title="ask claude about this name" statusDotColor="accent">
              <Textarea value={ask} onChange={(e) => setAsk(e.target.value)} rows={3} placeholder={`what do you want to know about ${ticker}?`} />
              <div className="mt-2 flex justify-end">
                <Button
                  disabled={!ask.trim() || runSkill.isPending}
                  onClick={() => {
                    run("ask_anything", { question: `About ${ticker} (${data.name}): ${ask.trim()}` }, `Ask ${ticker}`)
                    setAsk("")
                  }}
                >
                  ask claude
                </Button>
              </div>
            </Panel>

            {/* Skill dialogs */}
            <TwoFieldDialog
              open={valOpen}
              onOpenChange={setValOpen}
              title={`valuation review — ${ticker.toLowerCase()}`}
              fieldA={{ label: "your valuation summary", multiline: true }}
              fieldB={{ label: "peers (comma-separated)", multiline: false }}
              onSubmit={(a, b) => run("valuation_reviewer", { ticker, your_valuation_summary: a, peers: b }, `Valuation ${ticker}`)}
            />
            <TwoFieldDialog
              open={modelOpen}
              onOpenChange={setModelOpen}
              title={`build model — ${ticker.toLowerCase()}`}
              fieldA={{ label: "latest filings summary", multiline: true }}
              fieldB={{ label: "assumptions", multiline: true }}
              onSubmit={(a, b) => run("model_builder", { ticker, latest_filings_summary: a, assumptions: b }, `Model ${ticker}`)}
            />
            <TwoFieldDialog
              open={peersOpen}
              onOpenChange={setPeersOpen}
              title={`compare to peers — ${ticker.toLowerCase()}`}
              fieldA={{ label: "peers (comma-separated)", multiline: false }}
              onSubmit={(a) => run("compare_to_peers", { ticker, peers: a }, `Peers ${ticker}`)}
            />
          </>
        )}
      </div>
    </div>
  )
}

/** Small dialog collecting one or two skill argument fields. */
function TwoFieldDialog({
  open,
  onOpenChange,
  title,
  fieldA,
  fieldB,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  fieldA: { label: string; multiline: boolean }
  fieldB?: { label: string; multiline: boolean }
  onSubmit: (a: string, b: string) => void
}) {
  const [a, setA] = useState("")
  const [b, setB] = useState("")
  const valid = a.trim() && (!fieldB || b.trim())

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o)
        if (!o) {
          setA("")
          setB("")
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <div className="label mb-1">{fieldA.label}</div>
            {fieldA.multiline ? (
              <Textarea value={a} onChange={(e) => setA(e.target.value)} rows={4} />
            ) : (
              <Input value={a} onChange={(e) => setA(e.target.value)} mono />
            )}
          </div>
          {fieldB && (
            <div>
              <div className="label mb-1">{fieldB.label}</div>
              {fieldB.multiline ? (
                <Textarea value={b} onChange={(e) => setB(e.target.value)} rows={4} />
              ) : (
                <Input value={b} onChange={(e) => setB(e.target.value)} mono />
              )}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            cancel
          </Button>
          <Button
            disabled={!valid}
            onClick={() => {
              onSubmit(a.trim(), b.trim())
              onOpenChange(false)
              setA("")
              setB("")
            }}
          >
            run
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
