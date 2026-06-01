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
import {
  useIdeaWorkspace,
  useRunStage,
  useRunAllStages,
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
                <h1 className="text-2xl font-semibold tracking-tight">{ws.name}</h1>
                <div className="mt-1 flex items-center gap-4 text-sm text-text-secondary">
                  <span>score: {parseField(ws.master, "score") ?? "—"}</span>
                  <span>
                    recommendation: {parseField(ws.master, "recommendation") ?? "—"}
                  </span>
                </div>
              </div>
              <Tag variant={complete ? "success" : "accent"}>
                <StatusDot color={complete ? "success" : "accent"} />
                {complete ? "complete" : "in progress"}
              </Tag>
            </div>

            {/* 2. Stage progress strip */}
            <Panel
              title="validation progress"
              meta={`${ws.stages_complete}/${ws.total_stages}`}
              statusDotColor="accent"
            >
              <StageStrip complete={ws.stages_complete} total={ws.total_stages} />
            </Panel>

            {/* 3. Run controls */}
            <RunControls name={ideaName} stages={ws.stages} />

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
function RunControls({ name, stages }: { name: string; stages: IdeaStage[] }) {
  const runAll = useRunAllStages(name)
  const runStage = useRunStage(name)

  function started(runId?: string) {
    toast.success("started in background — see background runs", runId)
  }

  return (
    <Panel title="run controls" statusDotColor="accent">
      <div className="mb-3">
        <Button
          onClick={() =>
            runAll.mutate(undefined, {
              onSuccess: (r) => started(r.run_id),
              onError: (e) => toast.error("failed to start", String(e)),
            })
          }
          disabled={runAll.isPending}
        >
          run full validation
        </Button>
      </div>
      <div className="grid gap-1.5 sm:grid-cols-2">
        {stages.map((s) => (
          <div
            key={s.stage_key}
            className="flex items-center justify-between gap-2 rounded-sm px-2 py-1 hover:bg-bg-panel-hover"
          >
            <span className="flex items-center gap-2 min-w-0">
              <StatusDot color={STAGE_DOT[s.status]} />
              <span className="truncate text-sm text-text">{s.title}</span>
            </span>
            <Button
              variant="ghost"
              size="sm"
              disabled={runStage.isPending}
              onClick={() =>
                runStage.mutate(s.stage_key, {
                  onSuccess: (r) => started(r.run_id),
                  onError: (e) => toast.error("failed to start", String(e)),
                })
              }
            >
              {s.exists ? "re-run" : "run"}
            </Button>
          </div>
        ))}
      </div>
    </Panel>
  )
}

// 4. Per-stage output
function StageOutput({ name, stage }: { name: string; stage: IdeaStage }) {
  const isMarkdown = stage.filename.toLowerCase().endsWith(".md")
  const meta = stage.status + (stage.mtime ? ` · ${stage.mtime.slice(0, 10)}` : "")

  return (
    <Collapsible title={stage.title} meta={meta}>
      {!stage.exists ? (
        <p className="text-sm text-text-label">not generated yet</p>
      ) : isMarkdown ? (
        <pre className="whitespace-pre-wrap font-mono text-xs text-text-secondary">
          {stage.content || "(empty)"}
        </pre>
      ) : (
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-text-secondary">
            {stage.filename}
          </span>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => openInOs(`${name}/${stage.filename}`)}
          >
            open in os
          </Button>
        </div>
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
