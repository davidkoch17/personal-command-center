import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Play, ExternalLink, Archive, RotateCcw, X } from "lucide-react"
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

/**
 * Skills & Agents Registry (System §1, N2). The full admin list of every skill
 * + agent: name, kind/domain, description, last-run health, with Run +
 * Disable/Enable. Disabling is soft (archive) — greyed and unrunnable, never lost.
 */
export function RegistryList() {
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
        <div className="divide-y divide-border">
          {filtered.map((e) => (
            <RegistryRow key={e.key} entry={e} />
          ))}
        </div>
      )}
    </Panel>
  )
}

function RegistryRow({ entry }: { entry: RegistryEntry }) {
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
              <Tag variant="muted">{entry.domain}</Tag>
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
