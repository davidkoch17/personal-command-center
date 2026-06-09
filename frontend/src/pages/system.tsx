import { useState } from "react"
import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { RefreshCw, ChevronRight, Square, RotateCcw } from "lucide-react"
import { api } from "@/lib/api"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Toggle } from "@/components/ui/toggle"
import { StatusDot, type StatusColor } from "@/components/ui/status-dot"
import { ErrorState } from "@/components/ui/error-state"
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table"
import { LogStream } from "@/components/runs/log-stream"
import { DiagnosticRow } from "@/components/settings/diagnostic-row"
import { RegistryList } from "@/components/system/registry-list"
import { useRuns, isRunActive, useCancelRun, useRestartRun } from "@/hooks/useRuns"
import { useSystemStatus, useClearCache } from "@/hooks/useSystem"
import { useDiagnostics } from "@/hooks/useDiagnostics"
import { useFinanceDiagnostics } from "@/hooks/useFinance"
import { useTheme, type Theme } from "@/hooks/useTheme"
import { toast } from "@/lib/toast-store"
import type { RunStatus } from "@/lib/types"
import { cn } from "@/lib/utils"

/**
 * System page (v2 Page 7). Merges Background Runs + Settings + diagnostics into
 * one operational surface, fronted by the new Skills & Agents Registry. Sections:
 * registry · background runs · diagnostics · settings.
 */
export function System() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">system</h1>

      {/* 1. Skills & Agents Registry (N2) */}
      <RegistryList />

      {/* 2. Background Runs monitor (+ cancel / restart) */}
      <BackgroundRunsSection />

      {/* 3. Diagnostics — live integrations + finance source freshness */}
      <DiagnosticsSection />
      <FinanceDataSourcesSection />

      {/* 4. Settings */}
      <SettingsSection />
    </div>
  )
}

// --- Background runs ---------------------------------------------------------

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

function BackgroundRunsSection() {
  const { data, isLoading, isError, isFetching, refetch } = useRuns()
  const runs = data?.runs ?? []
  const anyActive = runs.some((r) => isRunActive(r.status))

  return (
    <Panel title="background runs" statusDotColor={anyActive ? "accent" : "muted"} meta={`${runs.length}`}>
      <div className="mb-3 flex items-center justify-end gap-3">
        {anyActive && (
          <span className="flex items-center gap-1.5 text-xs text-text-secondary">
            <StatusDot color="accent" pulse /> auto-refreshing
          </span>
        )}
        <Button variant="secondary" size="sm" onClick={() => refetch()} disabled={isFetching}>
          <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} /> refresh
        </Button>
      </div>

      {isError ? (
        <ErrorState message="could not load runs. backend on :8000?" onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <p className="text-sm text-text-label">no background runs yet</p>
      ) : (
        <div className="space-y-2">
          {runs.map((run) => (
            <RunRow key={run.run_id} run={run} />
          ))}
        </div>
      )}
    </Panel>
  )
}

function RunRow({ run }: { run: RunStatus }) {
  const [open, setOpen] = useState(false)
  const cancel = useCancelRun()
  const restart = useRestartRun()
  const meta = statusMeta(run.status)
  const dur = duration(run)
  const active = isRunActive(run.status)

  return (
    <div className="rounded-sm border border-border bg-bg-panel p-3">
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          <ChevronRight
            className={cn("h-4 w-4 shrink-0 text-text-secondary transition-transform", open && "rotate-90")}
          />
          <StatusDot color={meta.color} pulse={meta.pulse} />
          <span className="truncate text-sm text-text">{run.label || run.run_id}</span>
        </button>
        <div className="flex shrink-0 items-center gap-3 font-mono text-xs text-text-secondary">
          {run.started_at && <span className="hidden sm:inline">{run.started_at.slice(0, 19).replace("T", " ")}</span>}
          {dur && <span>{dur}</span>}
          <span className="label">{meta.label}</span>
          {active ? (
            <Button
              variant="ghost"
              size="sm"
              disabled={cancel.isPending}
              title="cancel — kill the detached process"
              onClick={() =>
                cancel.mutate(run.run_id, {
                  onSuccess: (r) =>
                    r.ok
                      ? toast.success("run cancelled", run.label ?? run.run_id)
                      : toast.show("nothing to cancel", { detail: r.detail }),
                  onError: (e) => toast.error("could not cancel", String(e)),
                })
              }
            >
              <Square className="h-3.5 w-3.5" /> cancel
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              disabled={restart.isPending}
              title="restart — relaunch with the same inputs"
              onClick={() =>
                restart.mutate(run.run_id, {
                  onSuccess: (r) => toast.success("restarted", `run ${r.run_id}`),
                  onError: (e) => toast.error("could not restart", String(e)),
                })
              }
            >
              <RotateCcw className="h-3.5 w-3.5" /> restart
            </Button>
          )}
        </div>
      </div>

      {open && (
        <div className="mt-3 space-y-2">
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

// --- Diagnostics -------------------------------------------------------------

function DiagnosticsSection() {
  const [ran, setRan] = useState(false)
  const { data, isFetching, refetch } = useDiagnostics(ran)

  return (
    <Panel title="integration diagnostics" statusDotColor="accent">
      <div className="mb-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={isFetching}
          onClick={() => {
            setRan(true)
            refetch()
          }}
        >
          {isFetching ? "checking…" : "run health check"}
        </Button>
      </div>
      {data?.checks && (
        <div>
          {data.checks.map((c) => (
            <DiagnosticRow key={c.name} check={c} />
          ))}
        </div>
      )}
      <p className="mt-2 text-xs text-text-label">live integrations only (calendar · github · alpha vantage · kraken).</p>
    </Panel>
  )
}

function FinanceDataSourcesSection() {
  const [probe, setProbe] = useState(false)
  const { data, isFetching, refetch } = useFinanceDiagnostics(true, probe)

  return (
    <Panel title="finance data sources" statusDotColor="accent">
      <div className="mb-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={isFetching}
          onClick={() => {
            setProbe(true)
            refetch()
          }}
        >
          {isFetching ? "probing…" : "probe live sources"}
        </Button>
      </div>
      {data?.checks && (
        <div>
          {data.checks.map((c) => (
            <DiagnosticRow key={c.name} check={c} />
          ))}
        </div>
      )}
      <p className="mt-2 text-xs text-text-label">
        cache freshness shows instantly; "probe live sources" adds a yfinance + FX hit.
      </p>
    </Panel>
  )
}

// --- Settings ----------------------------------------------------------------

interface VoiceStatus {
  whisper_installed: boolean
  whisper_loaded: boolean
  piper_installed: boolean
}

function SettingsSection() {
  const status = useSystemStatus()
  const clear = useClearCache()
  const { theme, setTheme } = useTheme()
  const voice = useQuery({
    queryKey: ["voice-status"],
    queryFn: () => api.get<VoiceStatus>("/api/voice/status"),
    retry: false,
  })
  const dot = (ok: boolean | undefined) => (ok ? "bg-success" : "bg-text-label")

  return (
    <Panel title="settings" statusDotColor="muted">
      <Table>
        <TableBody>
          <TableRow>
            <TableCell className="text-text-secondary">vault path</TableCell>
            <TableCell className="font-mono text-xs">
              {status.isLoading ? <Skeleton className="h-4 w-64" /> : status.data?.vault_path ?? "—"}
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell className="text-text-secondary">finance source mtime</TableCell>
            <TableCell className="font-mono text-xs">
              {status.data?.finance_source_mtime
                ? String(status.data.finance_source_mtime).slice(0, 19).replace("T", " ")
                : "—"}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>

      {/* Theme — real dark/light toggle, persisted to localStorage. */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <div>
          <div className="text-sm text-text">theme</div>
          <div className="font-mono text-xs text-text-secondary">applies instantly · saved on this device</div>
        </div>
        <Toggle<Theme>
          value={theme}
          options={[
            { value: "dark", label: "dark" },
            { value: "light", label: "light" },
          ]}
          onChange={setTheme}
        />
      </div>

      {/* Voice status (read-only). */}
      <div className="mt-4 border-t border-border pt-4">
        <div className="mb-2 text-sm text-text">voice (jarvis)</div>
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <span className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${dot(voice.data?.whisper_installed)}`} />
            whisper {voice.data?.whisper_installed ? "installed" : "not installed"}
          </span>
          <span className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${dot(voice.data?.piper_installed)}`} />
            piper {voice.data?.piper_installed ? "installed" : "not installed"}
          </span>
          <Button variant="ghost" size="sm" asChild className="ml-auto">
            <Link to="/debug-jarvis">debug jarvis</Link>
          </Button>
        </div>
      </div>

      {/* Cache. */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <div className="text-sm text-text">cache</div>
        <Button
          variant="secondary"
          size="sm"
          disabled={clear.isPending}
          onClick={() =>
            clear.mutate(undefined, {
              onSuccess: (r) => toast.success("cache cleared", r.detail),
              onError: (e) => toast.error("could not clear cache", String(e)),
            })
          }
        >
          clear cache
        </Button>
      </div>
    </Panel>
  )
}
