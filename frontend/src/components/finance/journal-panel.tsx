import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Collapsible } from "@/components/ui/collapsible"
import { NumberDisplay } from "@/components/ui/number-display"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  useDecisions,
  useDecision,
  useLogDecision,
  useAddRetrospective,
  useHitRate,
  useAntiPortfolio,
  type DecisionSummaryRow,
  type LogDecisionRequest,
} from "@/hooks/useFinance"
import { toast } from "@/lib/toast-store"

const ACTIONS = ["buy", "sell", "add", "trim"]
const EMOTIONS = ["calm", "fomo", "fear", "greed", "boredom", "conviction", "doubt"]

function convictionColor(c: number | null): string {
  if (c == null) return "text-text-label"
  if (c >= 5) return "text-success"
  if (c >= 3) return "text-accent"
  return "text-warning"
}

/** Decision journal tab — hit rate, decision list, and a log-a-decision form. */
export function JournalTab() {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <HitRatePanel />
        <AntiPortfolioPanel />
      </div>
      <DecisionList />
      <Collapsible title="log a decision" meta="thesis · conviction · pre-mortem">
        <DecisionLogForm />
      </Collapsible>
    </div>
  )
}

export function HitRatePanel() {
  const { data, isLoading } = useHitRate(4)
  return (
    <Panel
      title="hypothesis hit rate"
      meta={data ? `${data.hypotheses_reviewed} closed` : undefined}
      statusDotColor={data?.hit_rate != null && data.hit_rate >= 0.5 ? "success" : "muted"}
    >
      {isLoading ? (
        <Skeleton className="h-20" />
      ) : !data || data.hypotheses_reviewed === 0 ? (
        <p className="text-sm text-text-label">
          no closed hypotheses yet — confirmed / weakened / retired ones show here (section 15).
        </p>
      ) : (
        <div className="flex flex-wrap items-end gap-8">
          <div>
            <div className="label mb-0.5">hit rate</div>
            <NumberDisplay
              value={data.hit_rate != null ? data.hit_rate * 100 : null}
              format="percent"
              emphasized
              className="text-2xl"
            />
          </div>
          <div>
            <div className="label mb-0.5">confirmed</div>
            <span className="font-mono text-xl text-success tabular-nums">{data.confirmed}</span>
          </div>
          <div>
            <div className="label mb-0.5">weakened</div>
            <span className="font-mono text-xl text-warning tabular-nums">{data.weakened}</span>
          </div>
        </div>
      )}
    </Panel>
  )
}

export function AntiPortfolioPanel() {
  const { data, isLoading } = useAntiPortfolio()
  const skips = data?.skips ?? []
  return (
    <Panel
      title="anti-portfolio"
      meta={data ? `${data.count} skipped · ${data.review_due.length} due review` : undefined}
      statusDotColor={data && data.review_due.length > 0 ? "warning" : "muted"}
    >
      {isLoading ? (
        <Skeleton className="h-20" />
      ) : skips.length === 0 ? (
        <p className="text-sm text-text-label">
          no skipped names logged — record names you considered but passed on (section 14).
        </p>
      ) : (
        <ul className="space-y-1.5 text-sm">
          {skips.slice(0, 6).map((s, i) => (
            <li key={i} className="flex items-start justify-between gap-2 border-b border-border/40 pb-1.5">
              <div className="min-w-0">
                <span className="font-mono text-accent">{s.ticker}</span>
                {s.name && <span className="ml-2 text-text-secondary">{s.name}</span>}
                {s.reason && <p className="truncate text-xs text-text-label">{s.reason}</p>}
              </div>
              <span className="shrink-0 font-mono text-xs text-text-secondary">{s.considered_date}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

export function DecisionList({ filterable = false }: { filterable?: boolean }) {
  const { data, isLoading } = useDecisions(200)
  const all = data?.decisions ?? []
  const [open, setOpen] = useState<DecisionSummaryRow | null>(null)
  const [actionFilter, setActionFilter] = useState("all")
  const [tickerQuery, setTickerQuery] = useState("")

  const decisions = all.filter((d) => {
    if (actionFilter !== "all" && d.action !== actionFilter) return false
    if (tickerQuery.trim() && !(d.ticker ?? "").toUpperCase().includes(tickerQuery.trim().toUpperCase()))
      return false
    return true
  })

  return (
    <Panel
      title="decision journal"
      meta={data ? `${decisions.length} of ${data.count}` : undefined}
      statusDotColor="accent"
    >
      {filterable && (
        <div className="mb-3 flex flex-wrap items-end gap-3">
          <div className="w-32">
            <div className="label mb-1">action</div>
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="h-9 w-full rounded-sm border border-border bg-bg-panel px-2 text-sm text-text"
            >
              <option value="all">all</option>
              {ACTIONS.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>
          <div className="w-40">
            <div className="label mb-1">ticker</div>
            <Input mono value={tickerQuery} onChange={(e) => setTickerQuery(e.target.value)} placeholder="filter…" />
          </div>
        </div>
      )}
      {isLoading ? (
        <Skeleton className="h-40" />
      ) : decisions.length === 0 ? (
        <p className="text-sm text-text-label">no decisions logged yet</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-text-label">
                <th className="py-1.5 pr-2 font-normal">date</th>
                <th className="py-1.5 px-2 font-normal">ticker</th>
                <th className="py-1.5 px-2 font-normal">action</th>
                <th className="py-1.5 px-2 text-right font-normal">conviction</th>
                <th className="py-1.5 px-2 font-normal">emotion</th>
                <th className="py-1.5 px-2 font-normal">retro</th>
                <th className="py-1.5 pl-2" />
              </tr>
            </thead>
            <tbody>
              {decisions.map((d) => (
                <tr key={d.filename} className="border-b border-border/40">
                  <td className="py-1.5 pr-2 font-mono text-xs text-text-secondary">{d.date}</td>
                  <td className="py-1.5 px-2 font-mono text-accent">{d.ticker ?? "—"}</td>
                  <td className="py-1.5 px-2 uppercase text-xs text-text-secondary">{d.action ?? "—"}</td>
                  <td className={`py-1.5 px-2 text-right font-mono tabular-nums ${convictionColor(d.conviction)}`}>
                    {d.conviction != null ? `${d.conviction}/6` : "—"}
                  </td>
                  <td className="py-1.5 px-2 text-text-secondary">{d.emotion ?? "—"}</td>
                  <td className="py-1.5 px-2">
                    <span className={d.has_retrospective ? "text-success" : "text-text-label"}>
                      {d.has_retrospective ? "✓" : "—"}
                    </span>
                  </td>
                  <td className="py-1.5 pl-2 text-right">
                    <button
                      type="button"
                      onClick={() => setOpen(d)}
                      className="font-mono text-xs text-text-secondary hover:text-accent"
                    >
                      view
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <DecisionDialog decision={open} onClose={() => setOpen(null)} />
    </Panel>
  )
}

function DecisionDialog({
  decision,
  onClose,
}: {
  decision: DecisionSummaryRow | null
  onClose: () => void
}) {
  const { data, isLoading } = useDecision(decision?.filename)
  const addRetro = useAddRetrospective()
  const [retro, setRetro] = useState("")
  const [wasRight, setWasRight] = useState(true)

  function submitRetro() {
    if (!decision || !retro.trim()) return
    addRetro.mutate(
      { filename: decision.filename, retro_text: retro.trim(), was_right: wasRight },
      {
        onSuccess: () => {
          setRetro("")
          toast.success("retrospective saved")
        },
        onError: (e) => toast.error("could not save", String(e)),
      },
    )
  }

  return (
    <Dialog open={!!decision} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{decision?.filename}</DialogTitle>
        </DialogHeader>
        {isLoading ? (
          <Skeleton className="h-64" />
        ) : (
          <pre className="max-h-[50vh] overflow-y-auto whitespace-pre-wrap rounded-sm border border-border bg-bg-panel p-3 font-mono text-xs text-text-secondary">
            {data?.content}
          </pre>
        )}
        {decision && !decision.has_retrospective && (
          <div className="space-y-2 border-t border-border pt-3">
            <div className="label">add retrospective</div>
            <Textarea
              value={retro}
              onChange={(e) => setRetro(e.target.value)}
              placeholder="what happened? right or wrong, and why?"
              rows={3}
            />
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setWasRight(true)}
                className={`rounded-sm border px-3 py-1 text-xs ${wasRight ? "border-success text-success" : "border-border text-text-secondary"}`}
              >
                thesis right
              </button>
              <button
                type="button"
                onClick={() => setWasRight(false)}
                className={`rounded-sm border px-3 py-1 text-xs ${!wasRight ? "border-danger text-danger" : "border-border text-text-secondary"}`}
              >
                thesis wrong
              </button>
            </div>
          </div>
        )}
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            close
          </Button>
          {decision && !decision.has_retrospective && (
            <Button disabled={!retro.trim() || addRetro.isPending} onClick={submitRetro}>
              save retrospective
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function DecisionLogForm({ onDone }: { onDone?: () => void }) {
  const log = useLogDecision()
  const [form, setForm] = useState<LogDecisionRequest>({
    ticker: "",
    action: "buy",
    quantity: 0,
    price: 0,
    rationale: "",
    conviction_score: 4,
    emotion: "calm",
    expected_return: null,
    expected_timeframe_months: null,
    thesis: "",
    risks: "",
    pre_mortem: "",
  })

  function set<K extends keyof LogDecisionRequest>(k: K, v: LogDecisionRequest[K]) {
    setForm((f) => ({ ...f, [k]: v }))
  }

  function submit() {
    if (!form.ticker.trim()) return
    log.mutate(
      { ...form, ticker: form.ticker.trim().toUpperCase() },
      {
        onSuccess: (r) => {
          toast.success("decision logged", r.filename)
          setForm((f) => ({ ...f, ticker: "", rationale: "", thesis: "", risks: "", pre_mortem: "" }))
          onDone?.()
        },
        onError: (e) => toast.error("could not log", String(e)),
      },
    )
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="ticker">
          <Input mono value={form.ticker} onChange={(e) => set("ticker", e.target.value)} placeholder="GOOGL" />
        </Field>
        <Field label="action">
          <select
            value={form.action}
            onChange={(e) => set("action", e.target.value)}
            className="h-9 w-full rounded-sm border border-border bg-bg-panel px-2 text-sm text-text"
          >
            {ACTIONS.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </Field>
        <Field label="quantity">
          <Input
            mono
            type="number"
            value={form.quantity || ""}
            onChange={(e) => set("quantity", parseFloat(e.target.value) || 0)}
          />
        </Field>
        <Field label="price (€)">
          <Input
            mono
            type="number"
            value={form.price || ""}
            onChange={(e) => set("price", parseFloat(e.target.value) || 0)}
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="conviction (0–6)">
          <Input
            mono
            type="number"
            min={0}
            max={6}
            value={form.conviction_score}
            onChange={(e) => set("conviction_score", Math.max(0, Math.min(6, parseInt(e.target.value) || 0)))}
          />
        </Field>
        <Field label="emotion">
          <select
            value={form.emotion}
            onChange={(e) => set("emotion", e.target.value)}
            className="h-9 w-full rounded-sm border border-border bg-bg-panel px-2 text-sm text-text"
          >
            {EMOTIONS.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </Field>
        <Field label="expected return %">
          <Input
            mono
            type="number"
            value={form.expected_return != null ? form.expected_return * 100 : ""}
            onChange={(e) =>
              set("expected_return", e.target.value === "" ? null : (parseFloat(e.target.value) || 0) / 100)
            }
          />
        </Field>
        <Field label="timeframe (months)">
          <Input
            mono
            type="number"
            value={form.expected_timeframe_months ?? ""}
            onChange={(e) =>
              set("expected_timeframe_months", e.target.value === "" ? null : parseInt(e.target.value) || 0)
            }
          />
        </Field>
      </div>

      <Field label="thesis">
        <Textarea value={form.thesis} onChange={(e) => set("thesis", e.target.value)} rows={2} />
      </Field>
      <Field label="rationale">
        <Textarea value={form.rationale} onChange={(e) => set("rationale", e.target.value)} rows={2} />
      </Field>
      <Field label="risks">
        <Textarea value={form.risks} onChange={(e) => set("risks", e.target.value)} rows={2} />
      </Field>
      <Field label="pre-mortem (write the failure narrative before acting — section 16)">
        <Textarea value={form.pre_mortem} onChange={(e) => set("pre_mortem", e.target.value)} rows={2} />
      </Field>

      <div className="flex justify-end">
        <Button disabled={!form.ticker.trim() || log.isPending} onClick={submit}>
          log decision
        </Button>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="label mb-1">{label}</div>
      {children}
    </div>
  )
}
