import { useState } from "react"
import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Toggle } from "@/components/ui/toggle"
import {
  Table,
  TableBody,
  TableCell,
  TableRow,
} from "@/components/ui/table"
import { DiagnosticRow } from "@/components/settings/diagnostic-row"
import { useSystemStatus, useClearCache, useSystemConfig, useCheckpoints } from "@/hooks/useSystem"
import { useDiagnostics } from "@/hooks/useDiagnostics"
import { useFinanceDiagnostics } from "@/hooks/useFinance"
import { useTheme } from "@/hooks/useTheme"
import { openInOs } from "@/lib/open-in-os"
import { toast } from "@/lib/toast-store"

type BarrierMode = "auto" | "on" | "off"

const SHORTCUTS = [
  { keys: "cmd / ctrl + k", action: "open search palette" },
  { keys: "esc", action: "close palette / modal" },
  { keys: "click run row", action: "expand background-run log" },
]

export function Settings() {
  const status = useSystemStatus()

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">settings</h1>

      {/* 1. Paths */}
      <Panel title="paths" statusDotColor="muted">
        <Table>
          <TableBody>
            <TableRow>
              <TableCell className="text-text-secondary">vault</TableCell>
              <TableCell className="font-mono text-xs">
                {status.isLoading ? <Skeleton className="h-4 w-64" /> : status.data?.vault_path ?? "—"}
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="text-text-secondary">finance tracker</TableCell>
              <TableCell className="font-mono text-xs text-text-label">not exposed by api</TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="text-text-secondary">code repo</TableCell>
              <TableCell className="font-mono text-xs text-text-label">not exposed by api</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </Panel>

      {/* 1a. Last reconciliation checkpoint */}
      <CheckpointSection />

      {/* 1b. v3 configuration (capture paths · snapshot · watchlist · tailscale) */}
      <V3ConfigSection />

      {/* 2. Integration diagnostics */}
      <DiagnosticsSection />

      {/* 2b. Finance data-source health + cache freshness (Phase 15e) */}
      <FinanceDataSourcesSection />

      {/* 3. Info-barrier mode */}
      <InfoBarrierSection />

      {/* 3b. Voice (Jarvis) */}
      <VoiceSection />

      {/* 4. Theme */}
      <ThemeSection />

      {/* 5. Cache */}
      <CacheSection />

      {/* 6. Last file modifications */}
      <Panel title="last file modifications" statusDotColor="muted">
        <Table>
          <TableBody>
            <TableRow>
              <TableCell className="text-text-secondary">finance source</TableCell>
              <TableCell className="font-mono text-xs">
                {status.data?.finance_source_mtime
                  ? String(status.data.finance_source_mtime).slice(0, 19).replace("T", " ")
                  : "—"}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <p className="mt-2 text-xs text-text-label">per-file mtime table needs a key-files endpoint (pending)</p>
      </Panel>

      {/* 7. Keyboard shortcuts */}
      <Panel title="keyboard shortcuts" statusDotColor="muted">
        <Table>
          <TableBody>
            {SHORTCUTS.map((s) => (
              <TableRow key={s.keys}>
                <TableCell className="font-mono text-xs text-accent">{s.keys}</TableCell>
                <TableCell className="text-text-secondary">{s.action}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Panel>
    </div>
  )
}

/** Most recent reconciliation checkpoint (modules/system/checkpoints.py) — the
 * durable "we are here" marker so a new session knows where things stand. */
function CheckpointSection() {
  const { data, isLoading } = useCheckpoints()
  const latest = data?.latest

  return (
    <Panel title="last checkpoint" statusDotColor={latest ? "success" : "muted"}>
      {isLoading ? (
        <Skeleton className="h-10" />
      ) : !latest ? (
        <p className="text-sm text-text-label">no checkpoint recorded yet.</p>
      ) : (
        <div className="space-y-1">
          <div className="text-sm text-text">{latest.label}</div>
          <div className="font-mono text-xs text-text-secondary">
            {latest.timestamp.replace("T", " ")}
          </div>
          {latest.notes && <p className="text-xs text-text-label">{latest.notes}</p>}
        </div>
      )}
    </Panel>
  )
}

/** v3 configuration (spec § f): capture paths, snapshot time, watchlist, tailscale. */
function V3ConfigSection() {
  const { data, isLoading } = useSystemConfig()

  const Row = ({ k, v, openPath }: { k: string; v: string; openPath?: string }) => (
    <TableRow>
      <TableCell className="text-text-secondary">{k}</TableCell>
      <TableCell className="font-mono text-xs">
        {isLoading ? (
          <Skeleton className="h-4 w-64" />
        ) : openPath ? (
          <button
            type="button"
            onClick={() => openInOs(openPath)}
            className="text-left text-accent hover:underline"
            title="open in os"
          >
            {v}
          </button>
        ) : (
          v
        )}
      </TableCell>
    </TableRow>
  )

  return (
    <Panel title="v3 configuration" statusDotColor="accent">
      <Table>
        <TableBody>
          <Row k="capture — news" v={data?.capture_paths.news_captures ?? "—"} openPath={data?.capture_paths.news_captures} />
          <Row k="capture — voice" v={data?.capture_paths.voice_notes ?? "—"} openPath={data?.capture_paths.voice_notes} />
          <Row k="capture — finance imports" v={data?.capture_paths.finance_imports ?? "—"} openPath={data?.capture_paths.finance_imports} />
          <Row k="capture watcher" v={data ? `every ${data.capture_paths.watcher_interval_seconds}s` : "—"} />
          <Row k="daily snapshot" v={data ? `${data.snapshot.time} · ${data.snapshot.scheduler}` : "—"} />
          <Row k="watchlist tiers" v={data ? data.watchlist.tiers.join(" · ") : "—"} />
          <Row k="watchlist file" v={data?.watchlist.file ?? "—"} openPath={data?.watchlist.file} />
          <Row
            k="tailscale"
            v={data ? (data.tailscale.configured ? "configured" : data.tailscale.note) : "—"}
          />
          <Row k="evercore start" v={data?.evercore_start ?? "—"} />
        </TableBody>
      </Table>
      <p className="mt-2 text-xs text-text-label">
        active config values (read-only) — capture paths &amp; snapshot time are code / task-scheduler constants.
      </p>
    </Panel>
  )
}

/** Functional dark/light theme toggle (uses the live useTheme hook). */
function ThemeSection() {
  const { theme, setTheme } = useTheme()
  return (
    <Panel title="theme" statusDotColor="accent">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="h-6 w-6 rounded-sm border border-border" style={{ background: "#2563EB" }} />
          <div>
            <div className="text-sm text-text">cockpit</div>
            <div className="font-mono text-xs text-text-secondary">accent #2563EB</div>
          </div>
        </div>
        <Toggle<"dark" | "light">
          value={theme}
          options={[
            { value: "dark", label: "dark" },
            { value: "light", label: "light" },
          ]}
          onChange={setTheme}
        />
      </div>
    </Panel>
  )
}

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
    </Panel>
  )
}

function FinanceDataSourcesSection() {
  // Cache-freshness checks render immediately; the live network probe (yfinance
  // + FX) runs only when the user asks, so the panel never blocks on the network.
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

function InfoBarrierSection() {
  const [mode, setMode] = useState<BarrierMode>("auto")
  return (
    <Panel title="info-barrier mode" statusDotColor="warning">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-text-secondary">
          “i'm at evercore” — auto compares today to the start date.
        </p>
        <Toggle<BarrierMode>
          value={mode}
          options={[
            { value: "auto", label: "auto" },
            { value: "on", label: "on" },
            { value: "off", label: "off" },
          ]}
          onChange={(v) => {
            setMode(v)
            toast.show("settings-write endpoint pending", {
              detail: `set INFO_BARRIER=${v} in .env for now`,
            })
          }}
        />
      </div>
    </Panel>
  )
}

interface VoiceStatus {
  whisper_installed: boolean
  whisper_loaded: boolean
  piper_installed: boolean
}

function VoiceSection() {
  const [wakeWord, setWakeWord] = useState<"off" | "on">("off")
  const status = useQuery({
    queryKey: ["voice-status"],
    queryFn: () => api.get<VoiceStatus>("/api/voice/status"),
    retry: false,
  })

  const dot = (ok: boolean | undefined) =>
    ok ? "bg-success" : "bg-text-label"

  return (
    <Panel title="voice (jarvis)" statusDotColor="accent">
      <p className="mb-3 text-sm text-text-secondary">
        hold the bottom-center bar to talk. local whisper transcribes, claude
        routes the command, piper speaks back.
      </p>
      <div className="mb-3 flex flex-wrap gap-4 text-xs">
        <span className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${dot(status.data?.whisper_installed)}`} />
          whisper {status.data?.whisper_installed ? "installed" : "not installed"}
        </span>
        <span className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${dot(status.data?.piper_installed)}`} />
          piper {status.data?.piper_installed ? "installed" : "not installed"}
        </span>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-text-secondary">
          wake word (“hey claude”) — future; push-to-talk for now.
        </p>
        <Toggle<"off" | "on">
          value={wakeWord}
          options={[
            { value: "off", label: "off" },
            { value: "on", label: "on" },
          ]}
          onChange={(v) => {
            setWakeWord(v)
            toast.show("wake word not wired yet", {
              detail: "phase 13 ships push-to-talk; porcupine toggle is future",
            })
          }}
        />
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
        <p className="text-sm text-text-secondary">
          test jarvis routing with typed commands (no mic).
        </p>
        <Button variant="secondary" size="sm" asChild>
          <Link to="/debug-jarvis">debug jarvis</Link>
        </Button>
      </div>
    </Panel>
  )
}

function CacheSection() {
  const clear = useClearCache()
  return (
    <Panel title="cache" statusDotColor="muted">
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
    </Panel>
  )
}
