import { useState } from "react"
import { ArrowUpRight, FileText, Lightbulb } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Collapsible } from "@/components/ui/collapsible"
import { StageStrip } from "@/components/cards/stage-strip"
import { ProjectCard } from "@/components/cards/project-card"
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
import { useProjects, useCreateProject, useLatestBriefing } from "@/hooks/useProjects"
import { useIdeas } from "@/hooks/useIdeas"
import type { ProjectCard as ProjectCardData } from "@/lib/types"
import { formatBoth, formatRelative } from "@/lib/dates"
import { toast } from "@/lib/toast-store"

// The four pillar cards, in the locked spec order (§ e). Personal Brand (05)
// opens the Brand site instead of the generic project workspace.
const PILLAR_IDS = ["02", "03", "06", "05"]
const BRAND_ID = "05"

export function Projects() {
  const { data, isLoading, isError } = useProjects()
  const [newOpen, setNewOpen] = useState(false)

  const projects = data ?? []
  const byId = new Map(projects.map((p) => [p.id, p]))
  const pillar = PILLAR_IDS.map((id) => byId.get(id)).filter(
    (p): p is ProjectCardData => !!p,
  )
  const others = projects.filter(
    (p) => !PILLAR_IDS.includes(p.id) && p.folder !== "archived",
  )

  // Summary strip: active count · total open tasks · next hard date.
  const totalOpenTasks = pillar.reduce((n, p) => n + (p.open_task_count ?? 0), 0)
  const nextHardDate = pillar
    .map((p) => p.big_milestone_date)
    .filter((d): d is string => !!d)
    .sort()[0]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">projects</h1>
        <Button onClick={() => setNewOpen(true)}>+ new project</Button>
      </div>

      {/* Summary strip */}
      <div className="grid grid-cols-3 gap-3">
        <Stat label="active" value={String(pillar.length)} />
        <Stat label="open tasks" value={String(totalOpenTasks)} />
        <Stat
          label="next hard date"
          value={nextHardDate ? formatBoth(nextHardDate) : "—"}
        />
      </div>

      {isError && (
        <Panel title="error" statusDotColor="danger">
          <p className="text-text-secondary">
            could not load projects. is the backend running on :8000?
          </p>
        </Panel>
      )}

      {/* ProjectsGrid — 4 pillar cards */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {pillar.map((p) => (
            <ProjectCard
              key={p.id}
              project={p}
              href={p.id === BRAND_ID ? "/brand" : undefined}
              newTab={p.id !== BRAND_ID}
            />
          ))}
        </div>
      )}

      {/* Ideas pipeline entry + Weekly briefing */}
      <div className="grid gap-4 lg:grid-cols-2">
        <IdeasEntry />
        <BriefingCardPanel />
      </div>

      {others.length > 0 && (
        <Collapsible title="other projects" meta={`${others.length}`}>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {others.map((p) => (
              <ProjectCard key={p.id} project={p} />
            ))}
          </div>
        </Collapsible>
      )}

      <NewProjectDialog open={newOpen} onOpenChange={setNewOpen} />
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="panel flex flex-col gap-1">
      <span className="label">{label}</span>
      <span className="text-lg font-semibold tabular-nums text-text">{value}</span>
    </div>
  )
}

/** Ideas / Validation Pipeline entry — links to the Ideas site (spec § e). */
function IdeasEntry() {
  const { data, isLoading } = useIdeas()
  const ideas = data ?? []
  const running = ideas.filter((i) => i.state?.["_running"] != null).length

  return (
    <a
      href="/ideas"
      className="panel panel-hover group flex flex-col gap-3 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="flex items-center gap-2 text-sm font-medium text-text">
          <Lightbulb className="h-4 w-4 text-accent" />
          <span className="capitalize">idea validation pipeline</span>
        </span>
        <ArrowUpRight className="h-4 w-4 shrink-0 text-text-label group-hover:text-accent transition-colors" />
      </div>
      {isLoading ? (
        <Skeleton className="h-16" />
      ) : ideas.length === 0 ? (
        <p className="text-sm text-text-label">no ideas in the pipeline yet.</p>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-3 text-xs text-text-secondary">
            <span className="font-mono">{ideas.length} ideas</span>
            {running > 0 && <span className="text-accent">· {running} running</span>}
          </div>
          <ul className="space-y-1.5">
            {ideas.slice(0, 4).map((i) => (
              <li key={i.name} className="space-y-1">
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="truncate text-text">{i.name}</span>
                  <span className="shrink-0 font-mono text-text-label">
                    {Math.min(i.stages_complete, 12)}/12
                  </span>
                </div>
                <StageStrip complete={i.stages_complete} total={12} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </a>
  )
}

/** Small weekly-briefing card — reads 99_System/Briefings/ (spec § e). */
function BriefingCardPanel() {
  const { data, isLoading } = useLatestBriefing()

  return (
    <Panel
      title="weekly briefing"
      meta={data?.date ? formatRelative(data.date) : undefined}
      statusDotColor="accent"
    >
      {isLoading ? (
        <Skeleton className="h-16" />
      ) : !data || !data.path ? (
        <p className="text-sm text-text-label">no briefings on file yet.</p>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium text-text">
            <FileText className="h-4 w-4 text-text-label" />
            <span className="truncate">{data.title}</span>
          </div>
          {data.excerpt && (
            <p className="line-clamp-3 text-sm text-text-secondary">{data.excerpt}</p>
          )}
          <p className="font-mono text-[10px] text-text-label">
            {data.count} briefing{data.count === 1 ? "" : "s"} on file
          </p>
        </div>
      )}
    </Panel>
  )
}

function NewProjectDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const create = useCreateProject()
  const [name, setName] = useState("")
  const [flow, setFlow] = useState("A")
  const [seed, setSeed] = useState("")

  function reset() {
    setName("")
    setFlow("A")
    setSeed("")
  }

  function submit() {
    const trimmed = name.trim()
    if (!trimmed) return
    create.mutate(
      { name: trimmed, flow, seed: seed.trim() },
      {
        onSuccess: (r) => {
          toast.success("project created", r.folder)
          onOpenChange(false)
          reset()
        },
        onError: (e) => toast.error("could not create project", String(e)),
      },
    )
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o)
        if (!o) reset()
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>new project</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <div className="label mb-1">name</div>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="project name"
            />
          </div>
          <div>
            <div className="label mb-1">flow</div>
            <Select value={flow} onValueChange={setFlow}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="A">flow a</SelectItem>
                <SelectItem value="B">flow b</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <div className="label mb-1">seed (optional)</div>
            <Textarea
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              placeholder="initial context / brief..."
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            cancel
          </Button>
          <Button onClick={submit} disabled={!name.trim() || create.isPending}>
            create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
