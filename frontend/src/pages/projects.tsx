import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Collapsible } from "@/components/ui/collapsible"
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
import { useProjects, useCreateProject } from "@/hooks/useProjects"
import { toast } from "@/lib/toast-store"

export function Projects() {
  const { data, isLoading, isError } = useProjects()
  const [newOpen, setNewOpen] = useState(false)

  const active = (data ?? []).filter(
    (p) => p.status !== "done" && p.folder !== "archived",
  )
  const done = (data ?? []).filter((p) => p.status === "done")

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">projects</h1>
        <Button onClick={() => setNewOpen(true)}>+ new project</Button>
      </div>

      {isError && (
        <Panel title="error" statusDotColor="danger">
          <p className="text-text-secondary">
            could not load projects. is the backend running on :8000?
          </p>
        </Panel>
      )}

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {active.map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </div>
      )}

      {done.length > 0 && (
        <Collapsible title="done" meta={`${done.length}`}>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {done.map((p) => (
              <ProjectCard key={p.id} project={p} />
            ))}
          </div>
        </Collapsible>
      )}

      <NewProjectDialog open={newOpen} onOpenChange={setNewOpen} />
    </div>
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
