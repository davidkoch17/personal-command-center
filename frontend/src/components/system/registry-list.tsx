import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Play, ExternalLink, Archive, RotateCcw, X, FileClock, Clock } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tag } from "@/components/ui/tag"
import { Toggle } from "@/components/ui/toggle"
import { StatusDot, type StatusColor } from "@/components/ui/status-dot"
import { Skeleton } from "@/components/ui/skeleton"
import { ErrorState } from "@/components/ui/error-state"
import {
  useRegistry,
  useDisableEntry,
  useEnableEntry,
  type RegistryEntry,
} from "@/hooks/useRegistry"
import { useRunSkill } from "@/hooks/useSkills"
import { formatRelative } from "@/lib/dates"
import { toast } from "@/lib/toast-store"
import { cn } from "@/lib/utils"

const HEALTH_DOT: Record<RegistryEntry["health"], StatusColor> = {
  ok: "success",
  due: "warning",
  failed: "danger",
  never: "muted",
}

type KindFilter = "all" | "agent" | "skill"

/** Human cadence label from the registry's ``cadence_days`` (read-only schedule). */
function scheduleLabel(cadenceDays: number | null | undefined): string {
  if (cadenceDays == null) return "on demand"
  if (cadenceDays <= 1) return "daily"
  if (cadenceDays <= 7) return "weekly"
  if (cadenceDays <= 31) return "monthly"
  if (cadenceDays <= 92) return "quarterly"
  return `every ${cadenceDays}d`
}

/**
 * Skills & Agents Registry (System §1, N2 + v3 Background-Runs Tab 2). The full
 * catalog of every skill + agent grouped by domain: name, kind, description,
 * last-run health + schedule, with Run · View-output · Disable/Enable. Disabling
 * is soft (archive) — greyed and unrunnable, never lost.
 *
 * ``onViewOutput`` (Background-Runs Tab 2): when given, each entry with a last
 * run shows a "view output" button that jumps to the Runs tab for that run.
 */
export function RegistryList({
  onViewOutput,
}: {
  onViewOutput?: (runId: string) => void
} = {}) {
  const { data, isLoading, isError, refetch } = useRegistry()
  const [kind, setKind] = useState<KindFilter>("all")
  const [query, setQuery] = useState("")
  const [showDisabled, setShowDisabled] = useState(true)

  const entries = data?.entries ?? []
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return entries
      .filter((e) => (kind === "all" ? true : e.kind === kind))
      .filter((e) => (showDisabled ? true : !e.disabled))
      .filter((e) =>
        q
          ? e.label.toLowerCase().includes(q) ||
            e.key.toLowerCase().includes(q) ||
            e.domain.toLowerCase().includes(q) ||
            e.description.toLowerCase().includes(q)
          : true,
      )
      // Sort by domain, then disabled to the bottom of each group, then label.
      .sort(
        (a, b) =>
          a.domain.localeCompare(b.domain) ||
          Number(a.disabled) - Number(b.disabled) ||
          a.label.localeCompare(b.label),
      )
  }, [entries, kind, query, showDisabled])

  // Group the (already domain-sorted) filtered list into per-domain sections.
  const groups = useMemo(() => {
    const m = new Map<string, RegistryEntry[]>()
    for (const e of filtered) {
      const list = m.get(e.domain)
      if (list) list.push(e)
      else m.set(e.domain, [e])
    }
    return [...m.entries()]
  }, [filtered])

  const agentCount = entries.filter((e) => e.kind === "agent").length
  const skillCount = entries.length - agentCount
  const disabledCount = entries.filter((e) => e.disabled).length

  return (
    <Panel
      title="skills & agents registry"
      statusDotColor="accent"
      meta={`${agentCount} agents · ${skillCount} skills`}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Toggle<KindFilter>
          value={kind}
          options={[
            { value: "all", label: "all" },
            { value: "agent", label: "agents" },
            { value: "skill", label: "skills" },
          ]}
          onChange={setKind}
        />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="filter…"
          className="h-7 w-40 text-xs"
        />
        {disabledCount > 0 && (
          <button
            type="button"
            onClick={() => setShowDisabled((s) => !s)}
            className="ml-auto text-xs text-text-secondary hover:text-text"
          >
            {showDisabled ? "hide" : "show"} {disabledCount} disabled
          </button>
        )}
      </div>

      {isError ? (
        <ErrorState message="could not load the registry. backend on :8000?" onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-text-label">no matching skills or agents</p>
      ) : (
        <div className="space-y-4">
          {groups.map(([domain, rows]) => (
            <div key={domain}>
              <div className="mb-1 flex items-center gap-2 border-b border-border pb-1">
                <span className="label">{domain}</span>
                <span className="font-mono text-[10px] text-text-label">{rows.length}</span>
              </div>
              <div className="divide-y divide-border">
                {rows.map((e) => (
                  <RegistryRow key={e.key} entry={e} onViewOutput={onViewOutput} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  )
}

function RegistryRow({
  entry,
  onViewOutput,
}: {
  entry: RegistryEntry
  onViewOutput?: (runId: string) => void
}) {
  const run = useRunSkill()
  const disable = useDisableEntry()
  const enable = useEnableEntry()
  const [argOpen, setArgOpen] = useState(false)
  const [argValue, setArgValue] = useState("")

  function launch(args?: Record<string, unknown>) {
    run.mutate(
      { skill: entry.run_skill as string, args, label: entry.key },
      {
        onSuccess: (r) => {
          toast.success(`launched ${entry.label}`, `run ${r.run_id}`)
          setArgOpen(false)
          setArgValue("")
        },
        onError: (err) => toast.error(`could not launch ${entry.label}`, String(err)),
      },
    )
  }

  function onRun() {
    if (!entry.run_skill) return
    if (entry.prompt_arg) {
      setArgOpen((o) => !o)
      return
    }
    launch()
  }

  const lastRun = entry.last_run_at ? formatRelative(entry.last_run_at) : "never run"

  return (
    <div className={cn("py-2.5", entry.disabled && "opacity-55")}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <StatusDot color={entry.disabled ? "muted" : HEALTH_DOT[entry.health]} className="mt-1.5" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-text normal-case">{entry.label}</span>
              <Tag variant={entry.kind === "agent" ? "accent" : "muted"}>{entry.kind}</Tag>
              <Tag variant="muted">
                <Clock className="h-3 w-3" />
                {scheduleLabel(entry.cadence_days)}
              </Tag>
              {entry.disabled && <Tag variant="danger">disabled</Tag>}
            </div>
            <p className="mt-0.5 text-xs text-text-secondary">{entry.description}</p>
            <div className="mt-0.5 flex flex-wrap gap-x-3 font-mono text-[11px] text-text-label">
              <span>last: {lastRun}</span>
              {entry.health === "failed" && <span className="text-danger">last run failed</span>}
              {entry.note && !entry.disabled && <span>{entry.note}</span>}
              {entry.disabled && entry.disabled_at && (
                <span>archived {formatRelative(entry.disabled_at)}</span>
              )}
            </div>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {!entry.disabled && <RunAction entry={entry} onRun={onRun} pending={run.isPending} />}
          {onViewOutput && entry.last_run_id && (
            <Button
              variant="ghost"
              size="sm"
              title="view last output in the runs tab"
              onClick={() => onViewOutput(entry.last_run_id as string)}
            >
              <FileClock className="h-3.5 w-3.5" /> output
            </Button>
          )}
          {entry.disabled ? (
            <Button
              variant="secondary"
              size="sm"
              disabled={enable.isPending}
              onClick={() =>
                enable.mutate(entry.key, {
                  onSuccess: () => toast.success(`restored ${entry.label}`),
                })
              }
            >
              <RotateCcw className="h-3.5 w-3.5" /> restore
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              disabled={disable.isPending}
              title="soft-disable (archive) — reversible"
              onClick={() =>
                disable.mutate(
                  { key: entry.key },
                  { onSuccess: () => toast.show(`disabled ${entry.label}`, { detail: "archived — restore anytime" }) },
                )
              }
            >
              <Archive className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      {argOpen && entry.prompt_arg && (
        <div className="mt-2 flex items-center gap-2 pl-5">
          <Input
            autoFocus
            value={argValue}
            onChange={(e) => setArgValue(e.target.value)}
            placeholder={entry.prompt_arg}
            className="h-7 max-w-xs text-xs"
            onKeyDown={(e) => {
              if (e.key === "Enter" && argValue.trim())
                launch({ [entry.prompt_arg as string]: argValue.trim() })
            }}
          />
          <Button
            variant="primary"
            size="sm"
            disabled={run.isPending}
            onClick={() => launch(argValue.trim() ? { [entry.prompt_arg as string]: argValue.trim() } : {})}
          >
            run
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setArgOpen(false)}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}
    </div>
  )
}

/** The Run control: launch directly, prompt for an arg, or link to the owner. */
function RunAction({
  entry,
  onRun,
  pending,
}: {
  entry: RegistryEntry
  onRun: () => void
  pending: boolean
}) {
  if (entry.run_skill) {
    return (
      <Button variant="secondary" size="sm" disabled={pending} onClick={onRun}>
        <Play className="h-3.5 w-3.5" /> run
      </Button>
    )
  }
  if (entry.run_target) {
    return (
      <Button variant="secondary" size="sm" asChild>
        <Link to={entry.run_target}>
          <ExternalLink className="h-3.5 w-3.5" /> open
        </Link>
      </Button>
    )
  }
  return <span className="px-2 text-xs text-text-label">auto</span>
}
