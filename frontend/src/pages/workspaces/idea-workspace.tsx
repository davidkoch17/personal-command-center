import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Collapsible } from "@/components/ui/collapsible"
import { Tag } from "@/components/ui/tag"
import { StatusDot, type StatusColor } from "@/components/ui/status-dot"
import { StageStrip } from "@/components/cards/stage-strip"
import { useQueryClient } from "@tanstack/react-query"
import {
  useIdeaWorkspace,
  useRunStage,
  useRunAllStages,
  useRunRemainingStages,
  useDecideIdea,
  useUpdateOverrides,
  type IdeaStage,
} from "@/hooks/useIdeas"
import type { IdeaDecision } from "@/lib/types"
import { openInOs } from "@/lib/open-in-os"
import { toast } from "@/lib/toast-store"

const STAGE_DOT: Record<IdeaStage["status"], StatusColor> = {
  done: "success",
  stale: "warning",
  pending: "muted",
  running: "accent",
}

export function IdeaWorkspace() {
  const { name } = useParams<{ name: string }>()
  const ideaName = name ? decodeURIComponent(name) : undefined
  const { data: ws, isLoading, isError } = useIdeaWorkspace(ideaName)

  const complete = ws ? ws.stages_complete >= ws.total_stages : false

  return (
    <div className="min-h-screen bg-bg text-text p-6">
      <div className="mx-auto max-w-[1100px] space-y-5">
        <div className="flex items-center justify-between">
          <Link
            to="/ideas"
            className="font-mono text-xs text-text-secondary hover:text-accent"
          >
            ← ideas
          </Link>
          {ideaName && (
            <span className="font-mono text-xs text-text-label">{ideaName}</span>
          )}
        </div>

        {isError && (
          <Panel title="error" statusDotColor="danger">
            <p className="text-text-secondary">could not load idea “{ideaName}”.</p>
          </Panel>
        )}

        {isLoading && (
          <div className="space-y-4">
            <Skeleton className="h-16" />
            <Skeleton className="h-10" />
            <Skeleton className="h-40" />
          </div>
        )}

        {ws && ideaName && (
          <>
            {/* 1. Header */}
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight normal-case">{ws.name}</h1>
                <div className="mt-1 flex items-center gap-4 text-sm text-text-secondary">
                  <span>score: {parseField(ws.master, "score") ?? "—"}</span>
                  <span>
                    recommendation: {parseField(ws.master, "recommendation") ?? "—"}
                  </span>
                </div>
              </div>
              <Tag variant={complete ? "success" : "accent"}>
                <StatusDot
                  color={complete ? "success" : "accent"}
                  pulse={!!ws.running_stage}
                />
                {ws.running_stage
                  ? "validating…"
                  : complete
                    ? "complete"
                    : "in progress"}
              </Tag>
            </div>

            {/* 2. Stage progress strip */}
            <Panel
              title="validation progress"
              meta={
                ws.running_stage
                  ? `${ws.stages_complete}/${ws.total_stages} · running: ${stageTitle(ws.stages, ws.running_stage)}`
                  : `${ws.stages_complete}/${ws.total_stages}`
              }
              statusDotColor="accent"
            >
              <StageStrip complete={ws.stages_complete} total={ws.total_stages} />
            </Panel>

            {/* 3. Run controls */}
            <RunControls
              name={ideaName}
              stages={ws.stages}
              runningStage={ws.running_stage}
            />

            {/* 5. Idea Brief (always visible) */}
            <Panel title="idea brief — stage 1" statusDotColor="accent">
              {ws.brief ? (
                <pre className="whitespace-pre-wrap font-mono text-xs text-text-secondary">
                  {ws.brief}
                </pre>
              ) : (
                <p className="text-sm text-text-label">no brief yet</p>
              )}
            </Panel>

            {/* 4. Per-stage outputs */}
            <div className="space-y-3">
              {ws.stages.map((s) => (
                <StageOutput key={s.stage_key} name={ideaName} stage={s} />
              ))}
            </div>

            {/* 6. Overrides */}
            <OverridesSection name={ideaName} initial={ws.overrides} />

            {/* 7. Decision panel */}
            {complete && <DecisionPanel name={ideaName} />}
          </>
        )}
      </div>
    </div>
  )
}

// 3. Run controls
function RunControls({
  name,
  stages,
  runningStage,
}: {
  name: string
  stages: IdeaStage[]
  runningStage: string | null
}) {
  const qc = useQueryClient()
  const runAll = useRunAllStages(name)
  const runRemaining = useRunRemainingStages(name)
  const runStage = useRunStage(name)

  // One pipeline at a time per idea: while anything is in flight (or a launch
  // request is pending), every run button is disabled.
  const busy =
    !!runningStage ||
    runAll.isPending ||
    runRemaining.isPending ||
    runStage.isPending
  const allDone = stages.every((s) => s.status === "done")

  function started(runId?: string) {
    toast.success("started in background — see background runs", runId)
    // Pick up the runner's `_running` marker without waiting for the idle poll.
    qc.invalidateQueries({ queryKey: ["idea", name] })
  }

  const mutateOpts = {
    onSuccess: (r: { run_id: string }) => started(r.run_id),
    onError: (e: unknown) => toast.error("failed to start", String(e)),
  }

  return (
    <Panel title="run controls" statusDotColor="accent">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {!allDone && (
          <Button
            onClick={() => runRemaining.mutate(undefined, mutateOpts)}
            disabled={busy}
          >
            run remaining stages
          </Button>
        )}
        <Button
          variant={allDone ? "primary" : "secondary"}
          onClick={() => runAll.mutate(undefined, mutateOpts)}
          disabled={busy}
        >
          re-run full validation
        </Button>
        {runningStage && (
          <span className="flex items-center gap-1.5 text-xs text-text-secondary">
            <StatusDot color="accent" pulse />
            {stageTitle(stages, runningStage)} running — this page updates live
          </span>
        )}
      </div>
      <div className="grid gap-1.5 sm:grid-cols-2">
        {stages.map((s) => (
          <div
            key={s.stage_key}
            className="flex items-center justify-between gap-2 rounded-sm px-2 py-1 hover:bg-bg-panel-hover"
          >
            <span className="flex items-center gap-2 min-w-0">
              <StatusDot
                color={STAGE_DOT[s.status]}
                pulse={s.status === "running"}
              />
              <span className="truncate text-sm text-text">{s.title}</span>
            </span>
            {s.status === "running" ? (
              <span className="px-2 font-mono text-xs text-accent">running…</span>
            ) : (
              <Button
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={() => runStage.mutate(s.stage_key, mutateOpts)}
              >
                {s.exists ? "re-run" : "run"}
              </Button>
            )}
          </div>
        ))}
      </div>
    </Panel>
  )
}

/** Display title for a stage key, falling back to the raw key. */
function stageTitle(stages: IdeaStage[], stageKey: string): string {
  return stages.find((s) => s.stage_key === stageKey)?.title ?? `stage ${stageKey}`
}

// 4. Per-stage output
const QUALITY_META: Record<IdeaStage["quality"], { color: StatusColor; label: string }> = {
  valid: { color: "success", label: "valid" },
  corrupted: { color: "danger", label: "corrupted" },
  missing: { color: "muted", label: "missing" },
}

function StageOutput({ name, stage }: { name: string; stage: IdeaStage }) {
  const isMarkdown = stage.filename.toLowerCase().endsWith(".md")
  const q = QUALITY_META[stage.quality]
  const meta =
    `${q.label} · ${stage.status}` + (stage.mtime ? ` · ${stage.mtime.slice(0, 10)}` : "")

  return (
    <Collapsible title={stage.title} meta={meta}>
      {/* Output integrity flag (spec § e): valid · corrupted (refusal) · missing. */}
      <div className="mb-2 flex items-center justify-between gap-2">
        <Tag variant={q.color === "muted" ? "muted" : (q.color as "success" | "danger")}>
          <StatusDot color={q.color} />
          {q.label}
        </Tag>
        {stage.exists && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => openInOs(`${name}/${stage.filename}`)}
          >
            open output
          </Button>
        )}
      </div>
      {stage.quality === "corrupted" && (
        <p className="mb-2 text-xs text-danger">
          looks like a refusal / clarification reply, not a real stage doc — re-run this stage.
        </p>
      )}
      {!stage.exists ? (
        <p className="text-sm text-text-label">not generated yet</p>
      ) : isMarkdown ? (
        <pre className="whitespace-pre-wrap font-mono text-xs text-text-secondary">
          {stage.content || "(empty)"}
        </pre>
      ) : (
        <span className="font-mono text-xs text-text-secondary">{stage.filename}</span>
      )}
    </Collapsible>
  )
}

// 6. Overrides
function OverridesSection({ name, initial }: { name: string; initial: string }) {
  const update = useUpdateOverrides(name)
  const [text, setText] = useState(initial)
  // Re-sync when the loaded idea changes.
  useEffect(() => setText(initial), [initial])

  return (
    <Panel
      title="overrides"
      meta="respected by every stage"
      statusDotColor="warning"
    >
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="constraints / corrections the validator must respect..."
        rows={4}
      />
      <div className="mt-2 flex justify-end">
        <Button
          onClick={() =>
            update.mutate(text, {
              onSuccess: () => toast.success("overrides saved"),
              onError: (e) => toast.error("could not save", String(e)),
            })
          }
          disabled={update.isPending}
        >
          save overrides
        </Button>
      </div>
    </Panel>
  )
}

// 7. Decision panel
function DecisionPanel({ name }: { name: string }) {
  const decide = useDecideIdea(name)
  const [decision, setDecision] = useState<IdeaDecision>("Pursue")
  const [reason, setReason] = useState("")

  const options: IdeaDecision[] = ["Pursue", "Park", "Kill"]
  const reasonRequired = decision === "Kill"

  function submit() {
    if (reasonRequired && !reason.trim()) {
      toast.error("a kill reason is required")
      return
    }
    decide.mutate(
      { decision, reason: reason.trim() },
      {
        onSuccess: () => toast.success(`decision recorded: ${decision}`),
        onError: (e) => toast.error("could not record decision", String(e)),
      },
    )
  }

  return (
    <Panel title="decision" statusDotColor="accent">
      <div className="mb-3 flex gap-2">
        {options.map((o) => (
          <Button
            key={o}
            variant={decision === o ? "primary" : "secondary"}
            size="sm"
            onClick={() => setDecision(o)}
          >
            {o.toLowerCase()}
          </Button>
        ))}
      </div>
      <Textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder={reasonRequired ? "reason (required to kill)..." : "reason (optional)..."}
        rows={3}
      />
      <div className="mt-2 flex justify-end">
        <Button onClick={submit} disabled={decide.isPending}>
          record decision
        </Button>
      </div>
    </Panel>
  )
}

/** Best-effort scrape of a `score:` / `recommendation:` line from MASTER.md. */
function parseField(master: string, field: string): string | null {
  const re = new RegExp(`${field}\\s*[:=]\\s*(.+)`, "i")
  for (const line of master.split("\n")) {
    const m = line.match(re)
    if (m) return m[1].trim().replace(/\*+/g, "").slice(0, 40)
  }
  return null
}
