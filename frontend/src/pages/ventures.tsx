import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Collapsible } from "@/components/ui/collapsible"
import { ErrorState } from "@/components/ui/error-state"
import { ProjectCard } from "@/components/cards/project-card"
import { IdeaCard } from "@/components/cards/idea-card"
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
import { useProjects, useCreateProject } from "@/hooks/useProjects"
import { useIdeas, useCreateIdea } from "@/hooks/useIdeas"
import { toast } from "@/lib/toast-store"

/**
 * Ventures (v2 Page 4) — the boardroom. Absorbs the old Projects + Ideas pages
 * into ONE consistent overview: every venture and idea at a glance, three
 * clearly separated sections. Click a card → its tailored workspace (new tab):
 * a project opens the "department" (status + agent roster + log + run history),
 * an idea opens the 12-stage validator.
 *
 * Brand has its own page (v2 Page 6), so it's excluded from the venture set.
 */
function isBrand(folder: string, name: string): boolean {
  return folder.includes("05_Personal_Brand") || /\bbrand\b/i.test(name)
}

export function Ventures() {
  const projects = useProjects()
  const ideas = useIdeas()
  const [newVenture, setNewVenture] = useState(false)
  const [newIdea, setNewIdea] = useState(false)

  const allProjects = (projects.data ?? []).filter(
    (p) => !isBrand(p.folder, p.name),
  )
  const active = allProjects.filter(
    (p) => p.status !== "done" && p.folder !== "archived",
  )
  const done = allProjects.filter((p) => p.status === "done")
  const ideaList = ideas.data ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">ventures</h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setNewIdea(true)}>
            + new idea
          </Button>
          <Button onClick={() => setNewVenture(true)}>+ new venture</Button>
        </div>
      </div>

      {/* --- Active ventures --------------------------------------------- */}
      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="label">active ventures</h2>
          <span className="font-mono text-xs text-text-label">{active.length}</span>
        </div>
        {projects.isError ? (
          <ErrorState
            message="could not load ventures. is the backend running on :8000?"
            onRetry={() => projects.refetch()}
          />
        ) : projects.isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-40" />
            ))}
          </div>
        ) : active.length === 0 ? (
          <Panel title="active ventures" meta="0">
            <p className="text-sm text-text-label">
              no active ventures. start one with “+ new venture”.
            </p>
          </Panel>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {active.map((p) => (
              <ProjectCard key={p.id} project={p} />
            ))}
          </div>
        )}
      </section>

      {/* --- Ideas in validation ---------------------------------------- */}
      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="label">ideas in validation</h2>
          <span className="font-mono text-xs text-text-label">{ideaList.length}</span>
        </div>
        {ideas.isError ? (
          <ErrorState
            message="could not load ideas."
            onRetry={() => ideas.refetch()}
          />
        ) : ideas.isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }, (_, i) => (
              <Skeleton key={i} className="h-44" />
            ))}
          </div>
        ) : ideaList.length === 0 ? (
          <Panel title="ideas in validation" meta="0">
            <p className="text-sm text-text-label">
              no ideas in the pipeline. start one with “+ new idea”. on{" "}
              <span className="font-mono">pursue</span>, an idea spins up a Flow A
              venture with a starter agent roster.
            </p>
          </Panel>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {ideaList.map((idea) => (
              <IdeaCard key={idea.name} idea={idea} />
            ))}
          </div>
        )}
      </section>

      {/* --- Killed / parked -------------------------------------------- */}
      <Collapsible title="killed / parked" meta={`${done.length} done`}>
        <div className="space-y-3">
          {done.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {done.map((p) => (
                <ProjectCard key={p.id} project={p} />
              ))}
            </div>
          )}
          <p className="text-sm text-text-label">
            killed ideas are archived in the vault; the api lists active ideas
            only. parked ideas keep their validation artifacts under{" "}
            <span className="font-mono">98_Ideen</span>.
          </p>
        </div>
      </Collapsible>

      <NewVentureDialog open={newVenture} onOpenChange={setNewVenture} />
      <NewIdeaDialog open={newIdea} onOpenChange={setNewIdea} />
    </div>
  )
}

function NewVentureDialog({
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
          toast.success("venture created", r.folder)
          onOpenChange(false)
          reset()
        },
        onError: (e) => toast.error("could not create venture", String(e)),
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
          <DialogTitle>new venture</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <div className="label mb-1">name</div>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="venture name"
            />
          </div>
          <div>
            <div className="label mb-1">flow</div>
            <Select value={flow} onValueChange={setFlow}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="A">flow a — business venture</SelectItem>
                <SelectItem value="B">flow b — personal / decision</SelectItem>
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

function NewIdeaDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const create = useCreateIdea()
  const [name, setName] = useState("")
  const [brief, setBrief] = useState("")

  function reset() {
    setName("")
    setBrief("")
  }

  function submit() {
    const trimmed = name.trim()
    if (!trimmed) return
    create.mutate(
      { name: trimmed, brief_text: brief.trim() },
      {
        onSuccess: (r) => {
          toast.success("idea created", r.name)
          onOpenChange(false)
          reset()
        },
        onError: (e) => toast.error("could not create idea", String(e)),
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
          <DialogTitle>new idea</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <div className="label mb-1">name</div>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="idea name"
            />
          </div>
          <div>
            <div className="label mb-1">brief</div>
            <Textarea
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              placeholder="one-paragraph brief — the seed for stage 1..."
              rows={4}
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
