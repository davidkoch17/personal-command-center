import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Tag } from "@/components/ui/tag"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useDecisions, useLogDecision, type LogDecisionRequest } from "@/hooks/useFinance"
import { toast } from "@/lib/toast-store"

const ACTIONS = ["buy", "sell", "add", "trim"] as const
const EMOTIONS = ["calm", "conviction", "fomo", "fear", "greed", "uncertain"] as const

export interface DecisionPrefill {
  ticker?: string
  action?: string
  quantity?: number
  price?: number
}

/** The shared decision-log writer (model C). Used standalone in the Research tab
 *  AND opened as an auto-prompt after a Holdings trade. */
export function DecisionLogDialog({
  open,
  onOpenChange,
  prefill,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  prefill?: DecisionPrefill
}) {
  const log = useLogDecision()
  const [ticker, setTicker] = useState(prefill?.ticker ?? "")
  const [action, setAction] = useState<string>(prefill?.action ?? "buy")
  const [quantity, setQuantity] = useState(prefill?.quantity != null ? String(prefill.quantity) : "")
  const [price, setPrice] = useState(prefill?.price != null ? String(prefill.price) : "")
  const [conviction, setConviction] = useState("4")
  const [emotion, setEmotion] = useState<string>("calm")
  const [rationale, setRationale] = useState("")
  const [thesis, setThesis] = useState("")

  // Re-seed when a new prefill arrives (auto-prompt after a trade).
  const [seed, setSeed] = useState<string | undefined>(undefined)
  const key = open ? `${prefill?.ticker}-${prefill?.action}-${prefill?.quantity}-${prefill?.price}` : undefined
  if (open && key !== seed) {
    setSeed(key)
    setTicker(prefill?.ticker ?? "")
    setAction(prefill?.action ?? "buy")
    setQuantity(prefill?.quantity != null ? String(prefill.quantity) : "")
    setPrice(prefill?.price != null ? String(prefill.price) : "")
  }

  const valid = ticker.trim() && rationale.trim()

  function submit() {
    if (!valid) return
    const req: LogDecisionRequest = {
      ticker: ticker.trim().toUpperCase(),
      action,
      quantity: Number(quantity) || 0,
      price: Number(price) || 0,
      rationale: rationale.trim(),
      conviction_score: Number(conviction) || 0,
      emotion,
      thesis: thesis.trim(),
    }
    log.mutate(req, {
      onSuccess: () => {
        toast.success("decision logged", `${action} ${req.ticker}`)
        onOpenChange(false)
        setRationale("")
        setThesis("")
      },
      onError: (e) => toast.error("could not log decision", String(e)),
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>log decision</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <div className="label mb-1">ticker</div>
              <Input value={ticker} onChange={(e) => setTicker(e.target.value)} mono placeholder="NKE" />
            </div>
            <div>
              <div className="label mb-1">action</div>
              <Select value={action} onValueChange={setAction}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ACTIONS.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <div className="label mb-1">qty</div>
              <Input type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} mono />
            </div>
            <div>
              <div className="label mb-1">price</div>
              <Input type="number" value={price} onChange={(e) => setPrice(e.target.value)} mono />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="label mb-1">conviction (0–6)</div>
              <Input type="number" min={0} max={6} value={conviction} onChange={(e) => setConviction(e.target.value)} mono />
            </div>
            <div>
              <div className="label mb-1">emotion</div>
              <Select value={emotion} onValueChange={setEmotion}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {EMOTIONS.map((e) => <SelectItem key={e} value={e}>{e}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <div className="label mb-1">rationale</div>
            <Textarea value={rationale} onChange={(e) => setRationale(e.target.value)} rows={2} placeholder="why now…" />
          </div>
          <div>
            <div className="label mb-1">thesis (optional)</div>
            <Textarea value={thesis} onChange={(e) => setThesis(e.target.value)} rows={2} placeholder="the bet…" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>cancel</Button>
          <Button onClick={submit} disabled={!valid || log.isPending}>
            {log.isPending ? "logging…" : "log decision"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Decision-log list + manual add button (Research tab). */
export function DecisionLogPanel() {
  const { data, isLoading } = useDecisions(25)
  const [open, setOpen] = useState(false)

  return (
    <Panel
      title="decision log"
      meta={data ? `${data.count} entries` : undefined}
      statusDotColor="accent"
    >
      <div className="mb-3">
        <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>+ log decision</Button>
      </div>
      {isLoading ? (
        <Skeleton className="h-24" />
      ) : !data?.decisions.length ? (
        <p className="text-sm text-text-label">no decisions logged yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {data.decisions.map((d) => (
            <li key={d.filename} className="flex items-center gap-2 rounded-sm border border-border/60 px-2.5 py-1.5 text-sm">
              <span className="font-mono text-xs text-text-label">{d.date}</span>
              {d.ticker && <span className="font-mono text-text">{d.ticker}</span>}
              {d.action && <Tag variant="muted">{d.action}</Tag>}
              {d.conviction != null && <span className="text-xs text-text-secondary">conv {d.conviction}/6</span>}
              {d.has_retrospective && <Tag variant="success">retro</Tag>}
            </li>
          ))}
        </ul>
      )}
      <DecisionLogDialog open={open} onOpenChange={setOpen} />
    </Panel>
  )
}
