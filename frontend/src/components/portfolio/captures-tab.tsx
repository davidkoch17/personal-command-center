import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
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
import {
  useCaptures,
  useRouteCapture,
  type Capture,
} from "@/hooks/usePortfolioHub"
import { cn } from "@/lib/utils"
import { toast } from "@/lib/toast-store"

const STATUS_FILTERS = ["pending", "approved-auto", "approved", "archived", "all"] as const
type StatusFilter = (typeof STATUS_FILTERS)[number]

const CATEGORIES = ["news", "task", "park", "note"] as const

function statusTone(status: string | null): "muted" | "accent" | "success" | "warning" {
  if (status === "approved") return "success"
  if (status === "approved-auto") return "accent"
  if (status === "archived") return "muted"
  return "warning" // pending
}

export function CapturesTab() {
  const [filter, setFilter] = useState<StatusFilter>("pending")
  const captures = useCaptures(filter === "all" ? undefined : filter)
  const [selected, setSelected] = useState<Capture | null>(null)

  const counts = captures.data?.status_counts ?? {}

  return (
    <div className="space-y-4">
      {/* Filter chips — pending = David's triage queue (approval model B) */}
      <div className="flex flex-wrap gap-1.5">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={cn(
              "rounded-sm border px-3 py-1 text-xs lowercase transition-colors",
              filter === f
                ? "border-accent text-accent bg-bg-panel-hover"
                : "border-border text-text-secondary hover:text-text",
            )}
          >
            {f}
            {f !== "all" && counts[f] != null && (
              <span className="ml-1.5 font-mono text-text-label">{counts[f]}</span>
            )}
          </button>
        ))}
      </div>

      <Panel
        title="news captures"
        meta={captures.data ? `${captures.data.count} shown` : undefined}
        statusDotColor="accent"
      >
        {captures.isLoading ? (
          <Skeleton className="h-48" />
        ) : !captures.data?.captures.length ? (
          <p className="text-sm text-text-label">
            no captures in this view. the capture pipeline (iOS Shortcut → inbox → processing) feeds this.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-text-label">
                  <th className="py-2 pr-3 font-normal">date</th>
                  <th className="py-2 px-3 font-normal">topic</th>
                  <th className="py-2 px-3 font-normal">type</th>
                  <th className="py-2 px-3 font-normal">tickers</th>
                  <th className="py-2 px-3 font-normal">ai tags</th>
                  <th className="py-2 pl-3 font-normal">status</th>
                </tr>
              </thead>
              <tbody>
                {captures.data.captures.map((c) => {
                  const tags = Array.isArray(c.ai_tags) ? c.ai_tags : []
                  return (
                    <tr
                      key={c.id}
                      onClick={() => setSelected(c)}
                      className="cursor-pointer border-b border-border/50 last:border-0 hover:bg-bg-panel-hover"
                    >
                      <td className="py-2 pr-3 font-mono text-xs text-text-secondary">
                        {c.captured_at ? c.captured_at.slice(0, 10) : "—"}
                      </td>
                      <td className="max-w-[16rem] truncate py-2 px-3 text-text">{c.topic_tag || c.topic_slug || "—"}</td>
                      <td className="py-2 px-3">
                        <span className={cn("text-[11px] uppercase tracking-wider", c.type === "voice" ? "text-accent" : "text-text-label")}>
                          {c.type}
                        </span>
                      </td>
                      <td className="py-2 px-3 font-mono text-xs text-text-secondary">
                        {c.tickers.map((t) => t.ticker).join(", ") || "—"}
                      </td>
                      <td className="max-w-[14rem] truncate py-2 px-3 text-xs text-text-label">
                        {tags.slice(0, 4).map((t) => `#${String(t)}`).join(" ") || "—"}
                      </td>
                      <td className="py-2 pl-3">
                        <Tag variant={statusTone(c.status)}>{c.status ?? "pending"}</Tag>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <CaptureDetailModal capture={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

function CaptureDetailModal({ capture, onClose }: { capture: Capture | null; onClose: () => void }) {
  const route = useRouteCapture()
  const [category, setCategory] = useState<string>("")
  const [tickers, setTickers] = useState<string>("")
  const [taskText, setTaskText] = useState<string>("")

  // Sync local edit state when a new capture opens.
  const open = capture != null
  const capId = capture?.id
  // Initialize fields from the capture on first render of a new id.
  const [lastId, setLastId] = useState<string | undefined>(undefined)
  if (open && capId !== lastId) {
    setLastId(capId)
    setCategory(capture!.category || "news")
    setTickers(capture!.tickers.map((t) => t.ticker).join(", "))
    setTaskText("")
  }

  if (!capture) return null

  const body = capture.ocr_text || capture.voice_transcript || ""
  const tags = Array.isArray(capture.ai_tags) ? capture.ai_tags : []

  function buildTickerLinks() {
    return tickers
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean)
      .map((ticker) => ({ ticker, sector: null }))
  }

  function save(approve: boolean) {
    if (!capId) return
    route.mutate(
      {
        id: capId,
        req: {
          category,
          tickers: buildTickerLinks(),
          approve,
          task_text: category === "task" ? taskText || undefined : undefined,
        },
      },
      {
        onSuccess: () => {
          toast.success(approve ? "approved & routed" : "routing saved", capture!.topic_tag || capId!)
          onClose()
        },
        onError: (e) => toast.error("could not route capture", String(e)),
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{capture.topic_tag || capture.topic_slug || "capture"}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-xs text-text-label">
            <span className="font-mono">{capture.captured_at?.replace("T", " ").slice(0, 16)}</span>
            <Tag variant={capture.type === "voice" ? "accent" : "muted"}>{capture.type}</Tag>
            <Tag variant={statusTone(capture.status)}>{capture.status ?? "pending"}</Tag>
          </div>

          {/* OCR text / transcript */}
          <div>
            <div className="label mb-1">{capture.type === "voice" ? "transcript" : "ocr text"}</div>
            <div className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-sm border border-border bg-bg p-2.5 text-sm text-text-secondary">
              {body || <span className="text-text-label">no text extracted</span>}
            </div>
          </div>

          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {tags.map((t, i) => (
                <span key={i} className="text-xs text-text-label">#{String(t)}</span>
              ))}
            </div>
          )}

          {/* Editable routing */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="label mb-1">category (re-classify)</div>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <div className="label mb-1">tickers (comma-sep)</div>
              <Input value={tickers} onChange={(e) => setTickers(e.target.value)} mono placeholder="NKE, BABA" />
            </div>
          </div>

          {category === "task" && (
            <div>
              <div className="label mb-1">task text</div>
              <Input value={taskText} onChange={(e) => setTaskText(e.target.value)} placeholder="what to do…" />
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="secondary" onClick={() => save(false)} disabled={route.isPending}>
            save routing
          </Button>
          <Button onClick={() => save(true)} disabled={route.isPending}>
            {route.isPending ? "…" : "approve & route"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
