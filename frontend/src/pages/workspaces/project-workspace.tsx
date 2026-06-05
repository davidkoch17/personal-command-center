import { useState } from "react"
import { Link, useParams, useSearchParams } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Collapsible } from "@/components/ui/collapsible"
import { Tag } from "@/components/ui/tag"
import { TaskCheck } from "@/components/ui/task-check"
import { StatusDot } from "@/components/ui/status-dot"
import { useProjectWorkspace, useToggleNextStep } from "@/hooks/useProjects"
import { useRunSkill } from "@/hooks/useSkills"
import { useTasks } from "@/hooks/useTasks"
import type { ProjectStatus } from "@/lib/types"
import { projectStatusMeta } from "@/lib/status"
import { formatBoth } from "@/lib/dates"
import { openInOs } from "@/lib/open-in-os"
import { toast } from "@/lib/toast-store"

interface Milestone {
  text: string
  date?: string | null
}
interface NextStep {
  text: string
  checked: boolean
  line_index: number
}
interface KeyFile {
  path: string
  name: string
  mtime: string | null
  exists: boolean
}
interface Draft {
  name?: string
  path?: string
  modified?: string
  [k: string]: unknown
}
interface ProjectWorkspaceData {
  id: string
  name: string
  status: ProjectStatus
  status_text: string
  folder: string
  milestones: Milestone[]
  next_steps: NextStep[]
  key_files: KeyFile[]
  subfolders: string[]
  drafts: Draft[]
  readme_md: string
}

export function ProjectWorkspace() {
  const params = useParams<{ id: string }>()
  const [search] = useSearchParams()
  const id = params.id ?? search.get("id") ?? undefined

  const { data, isLoading, isError } = useProjectWorkspace(id)
  const ws = data as ProjectWorkspaceData | undefined

  return (
    <div className="min-h-screen bg-bg text-text p-6">
      <div className="mx-auto max-w-[1100px] space-y-5">
        <div className="flex items-center justify-between">
          <Link
            to="/projects"
            className="font-mono text-xs text-text-secondary hover:text-accent"
          >
            ← projects
          </Link>
          {id && (
            <span className="font-mono text-xs text-text-label">id: {id}</span>
          )}
        </div>

        {isError && (
          <Panel title="error" statusDotColor="danger">
            <p className="text-text-secondary">could not load project {id}.</p>
          </Panel>
        )}

        {isLoading && (
          <div className="space-y-4">
            <Skeleton className="h-16" />
            <Skeleton className="h-40" />
            <Skeleton className="h-40" />
          </div>
        )}

        {ws && id && (
          <>
            <WorkspaceHeader ws={ws} />
            <MilestonesSection milestones={ws.milestones} />
            <NextStepsSection id={id} steps={ws.next_steps} />
            <KeyFilesSection files={ws.key_files} />
            <SubfoldersSection subfolders={ws.subfolders} />
            <DraftsSection drafts={ws.drafts} />
            <AskClaudeSection id={id} />
            <TaggedTasksSection projectName={ws.name} projectId={id} />
            <DecisionsSection readme={ws.readme_md} />
            <Collapsible title="readme" meta={`${ws.readme_md.length} chars`}>
              <pre className="whitespace-pre-wrap font-mono text-xs text-text-secondary">
                {ws.readme_md || "(empty)"}
              </pre>
            </Collapsible>
          </>
        )}
      </div>
    </div>
  )
}

// 1. Header
function WorkspaceHeader({ ws }: { ws: ProjectWorkspaceData }) {
  const { color, label } = projectStatusMeta(ws.status)
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight normal-case">{ws.name}</h1>
        {ws.status_text && (
          <p className="mt-1 text-sm text-text-secondary">{ws.status_text}</p>
        )}
      </div>
      <Tag variant={color === "muted" ? "muted" : (color as "success" | "warning" | "danger" | "accent")}>
        <StatusDot color={color} />
        {label}
      </Tag>
    </div>
  )
}

// 2. Milestones (timeline if 3+)
function MilestonesSection({ milestones }: { milestones: Milestone[] }) {
  return (
    <Panel title="big milestones" meta={`${milestones.length}`} statusDotColor="accent">
      {milestones.length === 0 ? (
        <p className="text-sm text-text-label">no milestones</p>
      ) : (
        <ol className="space-y-2">
          {milestones.map((m, i) => (
            <li key={i} className="flex items-start gap-3">
              <div className="mt-1.5 flex flex-col items-center">
                <StatusDot color="accent" />
                {milestones.length >= 3 && i < milestones.length - 1 && (
                  <div className="mt-1 h-6 w-px bg-border" />
                )}
              </div>
              <div className="flex flex-1 items-baseline justify-between gap-2">
                <span className="text-sm text-text">{m.text}</span>
                <span className="shrink-0 font-mono text-xs text-text-secondary tabular-nums">
                  {m.date ? formatBoth(m.date) : ""}
                </span>
              </div>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  )
}

// 3. Next steps
function NextStepsSection({ id, steps }: { id: string; steps: NextStep[] }) {
  const toggle = useToggleNextStep(id)
  const open = steps.filter((s) => !s.checked).length
  return (
    <Panel title="next steps" meta={`${open} open`} statusDotColor="accent">
      {steps.length === 0 ? (
        <p className="text-sm text-text-label">no next steps in readme</p>
      ) : (
        <div className="space-y-0.5">
          {steps.map((s) => (
            <TaskCheck
              key={s.line_index}
              checked={s.checked}
              disabled={toggle.isPending}
              onToggle={() =>
                toggle.mutate(s.line_index, {
                  onError: (e) => toast.error("could not toggle", String(e)),
                })
              }
            >
              {s.text}
            </TaskCheck>
          ))}
        </div>
      )}
    </Panel>
  )
}

// 4. Key files
function KeyFilesSection({ files }: { files: KeyFile[] }) {
  return (
    <Panel title="key files" meta={`${files.length}`} statusDotColor="muted">
      {files.length === 0 ? (
        <p className="text-sm text-text-label">no key files defined</p>
      ) : (
        <ul className="space-y-1">
          {files.map((f) => (
            <li key={f.path} className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 min-w-0">
                <StatusDot color={f.exists ? "success" : "danger"} />
                <span className="truncate font-mono text-xs text-text">{f.name}</span>
              </span>
              <Button
                variant="ghost"
                size="sm"
                disabled={!f.exists}
                onClick={() => openInOs(f.path)}
              >
                open in os
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

// 5. Subfolders
function SubfoldersSection({ subfolders }: { subfolders: string[] }) {
  return (
    <Panel title="subfolders" meta={`${subfolders.length}`} statusDotColor="muted">
      {subfolders.length === 0 ? (
        <p className="text-sm text-text-label">no subfolders</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {subfolders.map((name) => (
            <Button
              key={name}
              variant="secondary"
              size="sm"
              onClick={() => openInOs(name)}
            >
              {name}
            </Button>
          ))}
        </div>
      )}
    </Panel>
  )
}

// 6. Drafts pending send
function DraftsSection({ drafts }: { drafts: Draft[] }) {
  return (
    <Panel title="drafts pending send" meta={`${drafts.length}`} statusDotColor="warning">
      {drafts.length === 0 ? (
        <p className="text-sm text-text-label">no drafts</p>
      ) : (
        <ul className="space-y-1">
          {drafts.map((d, i) => (
            <li key={i} className="flex items-center justify-between gap-2">
              <span className="truncate font-mono text-xs text-text">
                {d.name ?? d.path ?? "draft"}
              </span>
              {d.path && (
                <Button variant="ghost" size="sm" onClick={() => openInOs(d.path!)}>
                  open in os
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

// 7. Ask Claude
function AskClaudeSection({ id }: { id: string }) {
  const runSkill = useRunSkill()
  const [question, setQuestion] = useState("")

  function ask() {
    const q = question.trim()
    if (!q) return
    runSkill.mutate(
      { skill: "ask_about_project", args: { project_id: id, question: q }, label: `Ask project ${id}` },
      {
        onSuccess: (r) => {
          setQuestion("")
          toast.success("started in background — see background runs", r.run_id)
        },
        onError: (e) => toast.error("failed to start", String(e)),
      },
    )
  }

  return (
    <Panel title="ask claude about this project" statusDotColor="accent">
      <Textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="what do you want to know about this project?"
        rows={3}
      />
      <div className="mt-2 flex justify-end">
        <Button onClick={ask} disabled={!question.trim() || runSkill.isPending}>
          ask claude
        </Button>
      </div>
    </Panel>
  )
}

// 8. Tasks tagged with this project (heuristic: text mentions name or #id)
function TaggedTasksSection({
  projectName,
  projectId,
}: {
  projectName: string
  projectId: string
}) {
  const { data } = useTasks()
  const needle = projectName.toLowerCase()
  const tagged = Object.values(data ?? {})
    .flat()
    .filter(
      (t) =>
        t.text.toLowerCase().includes(needle) ||
        t.text.toLowerCase().includes(`#${projectId}`),
    )

  return (
    <Panel title="tasks tagged with this project" meta={`${tagged.length}`} statusDotColor="muted">
      {tagged.length === 0 ? (
        <p className="text-sm text-text-label">
          no tasks mention this project (matched by name / #{projectId})
        </p>
      ) : (
        <ul className="space-y-1 text-sm">
          {tagged.map((t, i) => (
            <li key={i} className="flex items-center gap-2">
              <StatusDot color={t.checked ? "success" : "muted"} />
              <span className={t.checked ? "text-text-secondary line-through" : "text-text"}>
                {t.text}
              </span>
              <span className="ml-auto font-mono text-xs text-text-label">{t.section}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

// 9. Decisions (parsed from README "## Decisions" if present)
function DecisionsSection({ readme }: { readme: string }) {
  const decisions = extractDecisions(readme)
  return (
    <Panel title="decisions" meta={`${decisions.length}`} statusDotColor="muted">
      {decisions.length === 0 ? (
        <p className="text-sm text-text-label">no decisions section in readme</p>
      ) : (
        <ul className="space-y-1 text-sm text-text-secondary">
          {decisions.map((d, i) => (
            <li key={i}>{d}</li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

/** Pull bullet lines under a "## Decisions" heading in the README, if any. */
function extractDecisions(readme: string): string[] {
  const lines = readme.split("\n")
  const out: string[] = []
  let inSection = false
  for (const line of lines) {
    if (/^#{1,6}\s+decisions\b/i.test(line.trim())) {
      inSection = true
      continue
    }
    if (inSection && /^#{1,6}\s/.test(line.trim())) break
    if (inSection) {
      const m = line.trim().match(/^[-*]\s+(.*)$/)
      if (m) out.push(m[1])
    }
  }
  return out
}
