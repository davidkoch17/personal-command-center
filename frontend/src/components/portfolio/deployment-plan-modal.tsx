import { useEffect, useState } from "react"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Toggle } from "@/components/ui/toggle"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  useCreateDeploymentPlan,
  useDeleteDeploymentPlan,
  useDeploymentPlans,
  useMarkTrancheExecuted,
  useUpdateDeploymentPlan,
  type DeploymentBucket,
  type DeploymentPlan,
} from "@/hooks/usePortfolioHub"
import { toast } from "@/lib/toast-store"
import { cn, formatCurrency } from "@/lib/utils"

export const BUCKET_LABEL: Record<DeploymentBucket, string> = {
  etf_foundation: "ETF Foundation",
  single_stocks: "Single Stocks",
  crypto: "Crypto",
  wild_cards: "Wild Cards",
}

export function targetLabel(p: Pick<DeploymentPlan, "target_bucket" | "target_ticker">): string {
  if (p.target_ticker) return p.target_ticker
  if (p.target_bucket) return BUCKET_LABEL[p.target_bucket]
  return "unassigned"
}

/** Local-calendar ISO date (toISOString would shift by the UTC offset near midnight). */
function isoDate(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

function addDays(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return isoDate(d)
}

function errText(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}

// --- Plan detail --------------------------------------------------------------------

/** Detail modal: schedule table, mark-executed sub-form, inline date edits, delete. */
export function DeploymentPlanModal({ planId, onClose }: { planId: string | null; onClose: () => void }) {
  // Looked up from the all-status list so the modal keeps working after the plan
  // completes (it then drops out of the "active" list the cards read).
  const { data } = useDeploymentPlans()
  const plan = data?.plans.find((p) => p.id === planId) ?? null

  // The plan can vanish underneath an open modal (deleted here, or elsewhere): once the
  // list has loaded and no longer has it, close instead of stranding an empty dialog.
  useEffect(() => {
    if (planId && data && !plan) onClose()
  }, [planId, data, plan, onClose])

  return (
    <Dialog open={!!planId} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        {plan ? <PlanBody plan={plan} onDeleted={onClose} /> : (
          <DialogHeader>
            <DialogTitle>deployment plan</DialogTitle>
          </DialogHeader>
        )}
      </DialogContent>
    </Dialog>
  )
}

function PlanBody({ plan, onDeleted }: { plan: DeploymentPlan; onDeleted: () => void }) {
  const update = useUpdateDeploymentPlan()
  const execute = useMarkTrancheExecuted()
  const del = useDeleteDeploymentPlan()
  const [executing, setExecuting] = useState<number | null>(null)
  const [amount, setAmount] = useState("")
  const [date, setDate] = useState(isoDate(new Date()))
  const [tradeId, setTradeId] = useState("")
  const [confirmDelete, setConfirmDelete] = useState(false)

  const pr = plan.progress

  function startExecute(i: number) {
    setExecuting(i)
    setAmount(String(Math.round((plan.total_eur * plan.schedule[i].pct) / 100)))
    setDate(isoDate(new Date()))
    setTradeId("")
  }

  function confirmExecute() {
    if (executing == null) return
    execute.mutate(
      { id: plan.id, index: executing, amount_eur: Number(amount), executed_date: date, trade_id: tradeId.trim() || undefined },
      {
        onSuccess: () => {
          toast.success("tranche marked executed", `${plan.name} · tranche ${executing + 1}`)
          setExecuting(null)
        },
        onError: (e) => toast.error("couldn't mark executed", errText(e)),
      },
    )
  }

  function changeDate(i: number, value: string) {
    if (!value || value === plan.schedule[i].target_date) return
    update.mutate(
      { id: plan.id, tranche_dates: { [i]: value } },
      { onError: (e) => toast.error("couldn't change the date", errText(e)) },
    )
  }

  // mutateAsync, not mutate({onSuccess}): deleting refetches the list, which unmounts this
  // component, and TanStack drops per-call callbacks once the caller has unmounted.
  async function remove() {
    try {
      await del.mutateAsync(plan.id)
      toast.success("plan deleted", plan.name)
      onDeleted()
    } catch (e) {
      toast.error("couldn't delete", errText(e))
    }
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>{plan.name}</DialogTitle>
        <p className="text-sm text-text-secondary">
          <span className="font-mono">{formatCurrency(plan.total_eur, "EUR", 0)}</span> → {targetLabel(plan)} ·{" "}
          <span className="font-mono">{pr.deployed_pct.toFixed(0)}%</span> deployed (
          {formatCurrency(pr.deployed_eur, "EUR", 0)}) ·{" "}
          <span
            className={cn(
              "rounded-sm border px-1 text-[10px] uppercase tracking-wider",
              plan.status === "complete" ? "border-success/30 text-success" : plan.status === "cancelled" ? "border-border text-text-label" : "border-invest/30 bg-invest/10 text-invest",
            )}
          >
            {plan.status.replace("_", " ")}
          </span>
        </p>
      </DialogHeader>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>tranche</TableHead>
            <TableHead>target date</TableHead>
            <TableHead>status</TableHead>
            <TableHead className="text-right">amount</TableHead>
            <TableHead>executed</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {plan.schedule.map((t, i) => (
            <TableRow key={`${i}-${t.target_date}-${t.executed}`}>
              <TableCell className="font-mono">
                {i + 1} · {t.pct}%
              </TableCell>
              <TableCell>
                {t.executed ? (
                  <span className="font-mono text-text-secondary">{t.target_date}</span>
                ) : (
                  <Input
                    type="date"
                    mono
                    className="h-8 w-40"
                    defaultValue={t.target_date}
                    onBlur={(e) => changeDate(i, e.target.value)}
                    aria-label={`target date for tranche ${i + 1}`}
                  />
                )}
              </TableCell>
              <TableCell>
                <span className={cn("text-xs", t.executed ? "text-success" : "text-text-label")}>
                  {t.executed ? "● executed" : "○ pending"}
                </span>
              </TableCell>
              <TableCell className="text-right font-mono tabular-nums">
                {t.executed ? formatCurrency(t.amount_eur, "EUR", 0) : "—"}
              </TableCell>
              <TableCell className="font-mono text-xs text-text-secondary">
                {t.executed ? (
                  <>
                    {t.executed_date}
                    {t.trade_id && <span className="ml-1 text-text-label">· {t.trade_id}</span>}
                  </>
                ) : (
                  "—"
                )}
              </TableCell>
              <TableCell className="text-right">
                {!t.executed && plan.status !== "cancelled" && (
                  <Button size="sm" variant="secondary" onClick={() => startExecute(i)}>
                    mark executed
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {executing != null && (
        <div className="rounded-sm border border-border bg-bg p-3">
          <div className="label mb-2">
            mark tranche {executing + 1} ({plan.schedule[executing].pct}%) executed
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-xs text-text-label">
              amount (€)
              <Input mono type="number" min="0" step="1" className="mt-1 w-32" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </label>
            <label className="text-xs text-text-label">
              executed on
              <Input mono type="date" className="mt-1 w-40" value={date} onChange={(e) => setDate(e.target.value)} />
            </label>
            <label className="text-xs text-text-label">
              trade id (optional)
              <Input mono className="mt-1 w-40" value={tradeId} onChange={(e) => setTradeId(e.target.value)} placeholder="transaction id" />
            </label>
            <Button size="sm" onClick={confirmExecute} disabled={execute.isPending || !(Number(amount) > 0)}>
              {execute.isPending ? "saving…" : "confirm"}
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setExecuting(null)}>
              cancel
            </Button>
          </div>
          <p className="mt-2 text-xs text-text-label">
            records the tranche only — it doesn't create a transaction; log the trade itself under Holdings.
          </p>
        </div>
      )}

      <DialogFooter className="flex-wrap gap-2">
        {confirmDelete ? (
          <>
            <span className="mr-auto self-center text-sm text-danger">delete "{plan.name}" permanently?</span>
            <Button variant="secondary" size="sm" onClick={() => setConfirmDelete(false)}>
              keep
            </Button>
            <Button size="sm" onClick={remove} disabled={del.isPending} className="bg-danger text-white hover:bg-danger/90">
              {del.isPending ? "deleting…" : "yes, delete"}
            </Button>
          </>
        ) : (
          <Button variant="secondary" size="sm" onClick={() => setConfirmDelete(true)} className="mr-auto text-danger">
            delete plan
          </Button>
        )}
      </DialogFooter>
    </>
  )
}

// --- New plan -------------------------------------------------------------------------

type TargetKind = "bucket" | "ticker" | "none"

interface DraftTranche {
  pct: string
  date: string
}

const defaultDraft = (): DraftTranche[] => [
  { pct: "50", date: addDays(0) },
  { pct: "30", date: addDays(28) },
  { pct: "20", date: addDays(63) },
]

/** New-plan modal: name, total, bucket-or-ticker target, and an editable 50/30/20 schedule. */
export function NewPlanModal({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const create = useCreateDeploymentPlan()
  const [name, setName] = useState("")
  const [total, setTotal] = useState("")
  const [kind, setKind] = useState<TargetKind>("bucket")
  const [bucket, setBucket] = useState<DeploymentBucket>("etf_foundation")
  const [ticker, setTicker] = useState("")
  const [draft, setDraft] = useState<DraftTranche[]>(defaultDraft)

  const pctSum = draft.reduce((s, t) => s + (Number(t.pct) || 0), 0)
  const sumOk = Math.abs(pctSum - 100) < 0.01
  const valid = name.trim() !== "" && Number(total) > 0 && sumOk && draft.every((t) => t.date) && (kind !== "ticker" || ticker.trim() !== "")

  function reset() {
    setName("")
    setTotal("")
    setKind("bucket")
    setBucket("etf_foundation")
    setTicker("")
    setDraft(defaultDraft())
  }

  function submit() {
    create.mutate(
      {
        name: name.trim(),
        total_eur: Number(total),
        target_bucket: kind === "bucket" ? bucket : null,
        target_ticker: kind === "ticker" ? ticker.trim().toUpperCase() : null,
        schedule: draft.map((t) => ({ pct: Number(t.pct), target_date: t.date })),
      },
      {
        onSuccess: (p) => {
          toast.success("plan created", p.name)
          reset()
          onOpenChange(false)
        },
        onError: (e) => toast.error("couldn't create the plan", errText(e)),
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>new deployment plan</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-xs text-text-label sm:col-span-1">
              name
              <Input className="mt-1" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Q1 ETF boost" autoFocus />
            </label>
            <label className="text-xs text-text-label">
              total (€)
              <Input mono type="number" min="0" step="100" className="mt-1" value={total} onChange={(e) => setTotal(e.target.value)} placeholder="10000" />
            </label>
          </div>

          <div>
            <div className="label mb-1.5">target</div>
            <div className="flex flex-wrap items-center gap-3">
              <Toggle
                value={kind}
                options={[
                  { value: "bucket", label: "bucket" },
                  { value: "ticker", label: "ticker" },
                  { value: "none", label: "none" },
                ]}
                onChange={setKind}
              />
              {kind === "bucket" && (
                <div className="w-48">
                  <Select value={bucket} onValueChange={(v) => setBucket(v as DeploymentBucket)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(BUCKET_LABEL).map(([k, l]) => (
                        <SelectItem key={k} value={k}>{l}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              {kind === "ticker" && (
                <Input mono className="w-40" value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="VWCE.DE" />
              )}
            </div>
          </div>

          <div>
            <div className="label mb-1.5">schedule</div>
            <div className="space-y-2">
              {draft.map((t, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="w-16 text-sm text-text-secondary">tranche {i + 1}</span>
                  <Input
                    mono type="number" min="0" className="w-20 text-right" value={t.pct}
                    onChange={(e) => setDraft((d) => d.map((x, j) => (j === i ? { ...x, pct: e.target.value } : x)))}
                    aria-label={`tranche ${i + 1} percent`}
                  />
                  <span className="text-xs text-text-label">%</span>
                  <Input
                    mono type="date" className="w-40" value={t.date}
                    onChange={(e) => setDraft((d) => d.map((x, j) => (j === i ? { ...x, date: e.target.value } : x)))}
                    aria-label={`tranche ${i + 1} date`}
                  />
                  <span className="font-mono text-xs text-text-label">
                    {Number(total) > 0 ? formatCurrency((Number(total) * (Number(t.pct) || 0)) / 100, "EUR", 0) : ""}
                  </span>
                </div>
              ))}
            </div>
            <p className={cn("mt-1.5 text-xs", sumOk ? "text-text-label" : "text-danger")}>
              {sumOk ? "50 / 30 / 20 over ~10 weeks by default — edit if needed" : `percentages sum to ${pctSum} — they must total 100`}
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>cancel</Button>
          <Button onClick={submit} disabled={!valid || create.isPending}>
            {create.isPending ? "creating…" : "create plan"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
