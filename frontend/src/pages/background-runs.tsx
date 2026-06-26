import { useEffect, useRef, useState } from "react"
import { RefreshCw, ChevronRight, X, RotateCcw } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusDot, type StatusColor } from "@/components/ui/status-dot"
import { ErrorState } from "@/components/ui/error-state"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { LogStream } from "@/components/runs/log-stream"
import { RegistryList } from "@/components/system/registry-list"
import { useRuns, useCancelRun, useRestartRun, isRunActive } from "@/hooks/useRuns"
import type { RunStatus } from "@/lib/types"
import { toast } from "@/lib/toast-store"
import { cn } from "@/lib/utils"

function statusMeta(status: string): { color: StatusColor; pulse: boolean; label: string } {
  const s = (status ?? "").toLowerCase()
  if (s === "completed" || s === "done") return { color: "success", pulse: false, label: "completed" }
  if (s === "failed" || s === "error") return { color: "danger", pulse: false, label: "failed" }
  if (s === "cancelled") return { color: "muted", pulse: false, label: "cancelled" }
  if (isRunActive(s)) return { color: "accent", pulse: true, label: "running" }
  return { color: "muted", pulse: false, label: s || "unknown" }
}

function duration(run: RunStatus): string | null {
  const end = run.completed_at ?? run.failed_at
  if (!run.started_at || !end) return null
  const ms = new Date(end).getTime() - new Date(run.started_at).getTime()
  if (Number.isNaN(ms) || ms < 0) return null
  const s = Math.round(ms / 1000)
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`
}

/**
 * Background Runs (v3, spec § f). Two tabs:
 *  - **runs** — recent background runs from 99_System/Background_Runs/ (tail the
 *    live log, cancel a running job, restart a finished one).
 *  - **skills & agents** — the catalog (config/skills_registry.yaml) grouped by
 *    domain; run · view last output (jumps here) · schedule.
 */
export function BackgroundRuns() {
  const [tab, setTab] = useState("runs")
  // Set by the catalog's "view output" button → opens that run on the Runs tab.
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">background runs</h1>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="runs">runs</TabsTrigger>
          <TabsTrigger value="catalog">skills &amp; agents</TabsTrigger>
        </TabsList>

        <TabsContent value="runs">
          <RunsTab selectedRunId={selectedRunId} />
        </TabsContent>

        <TabsContent value="catalog">
          <RegistryList
            onViewOutput={(runId) => {
              setSelectedRunId(runId)
              setTab("runs")
            }}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function RunsTab({ selectedRunId }: { selectedRunId: string | null }) {
  const { data, isLoading, isError, isFetching, refetch } = useRuns()
  const runs = data?.runs ?? []
  const anyActive = runs.some((r) => isRunActive(r.status))

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end gap-3">
        {anyActive && (
          <span className="flex items-center gap-1.5 text-xs text-text-secondary">
            <StatusDot color="accent" pulse /> auto-refreshing
          </span>
        )}
        <Button variant="secondary" size="sm" onClick={() => refetch()} disabled={isFetching}>
          <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} /> refresh
        </Button>
      </div>

      {isError && (
        <ErrorState message="could not load runs. backend on :8000?" onRetry={() => refetch()} />
      )}

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <Panel title="runs" meta="0">
          <p className="text-sm text-text-label">no background runs yet</p>
        </Panel>
      ) : (
        <div className="space-y-2">
          {runs.map((run) => (
            <RunRow key={run.run_id} run={run} highlight={run.run_id === selectedRunId} />
          ))}
        </div>
      )}
    </div>
  )
}

function RunRow({ run, highlight }: { run: RunStatus; highlight: boolean }) {
  const [open, setOpen] = useState(false)
  const rowRef = useRef<HTMLDivElement>(null)
  const cancel = useCancelRun()
  const restart = useRestartRun()
  const meta = statusMeta(run.status)
  const dur = duration(run)
  const active = isRunActive(run.status)

  // When the catalog's "view output" selects this run, open + scroll into view.
  useEffect(() => {
    if (highlight) {
      setOpen(true)
      rowRef.current?.scrollIntoView({ behavior: "smooth", block: "center" })
    }
  }, [highlight])

  return (
    <div ref={rowRef} className={cn("panel", highlight && "border-accent-dim")}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          <ChevronRight className={cn("h-4 w-4 shrink-0 text-text-secondary transition-transform", open && "rotate-90")} />
          <StatusDot color={meta.color} pulse={meta.pulse} />
          <span className="truncate text-sm text-text">{run.label || run.run_id}</span>
        </div>
        <div className="flex shrink-0 items-center gap-3 font-mono text-xs text-text-secondary">
          {run.started_at && <span>{run.started_at.slice(0, 19).replace("T", " ")}</span>}
          {dur && <span>{dur}</span>}
          <span className="label">{meta.label}</span>
        </div>
      </button>

      {open && (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            {active ? (
              <Button
                variant="secondary"
                size="sm"
                disabled={cancel.isPending}
                onClick={() =>
                  cancel.mutate(run.run_id, {
                    onSuccess: () => toast.success("run cancelled", run.run_id),
                    onError: (e) => toast.error("could not cancel", String(e)),
                  })
                }
              >
                <X className="h-3.5 w-3.5" /> cancel
              </Button>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                disabled={restart.isPending}
                onClick={() =>
                  restart.mutate(run.run_id, {
                    onSuccess: (r) => toast.success("restarted", r.run_id),
                    onError: (e) => toast.error("could not restart", String(e)),
                  })
                }
              >
                <RotateCcw className="h-3.5 w-3.5" /> restart
              </Button>
            )}
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-text-label">
            <span>id: {run.run_id}</span>
            {run.log_file && <span>log: {run.log_file}</span>}
          </div>
          {run.error && <p className="text-xs text-danger">{run.error}</p>}
          <LogStream runId={run.run_id} />
        </div>
      )}
    </div>
  )
}
