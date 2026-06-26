import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Collapsible } from "@/components/ui/collapsible"
import { ErrorState } from "@/components/ui/error-state"
import { IdeaCard } from "@/components/cards/idea-card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useIdeas, useCreateIdea, useKilledIdeas } from "@/hooks/useIdeas"
import { toast } from "@/lib/toast-store"

export function Ideas() {
  const { data, isLoading, isError, refetch } = useIdeas()
  const [newOpen, setNewOpen] = useState(false)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">ideas</h1>
        <Button onClick={() => setNewOpen(true)}>+ new idea</Button>
      </div>

      {isError && (
        <ErrorState message="could not load ideas. is the backend running on :8000?" onRetry={() => refetch()} />
      )}

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-44" />
          ))}
        </div>
      ) : (data ?? []).length === 0 ? (
        <Panel title="ideas" meta="0 active">
          <p className="text-sm text-text-label">
            no ideas yet. start one with “+ new idea”.
          </p>
        </Panel>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {(data ?? []).map((idea) => (
            <IdeaCard key={idea.name} idea={idea} />
          ))}
        </div>
      )}

      <KilledSection />

      <NewIdeaDialog open={newOpen} onOpenChange={setNewOpen} />
    </div>
  )
}

/** Collapsed killed-ideas archive (98_Ideen/_killed/). */
function KilledSection() {
  const { data } = useKilledIdeas()
  const killed = data ?? []
  if (killed.length === 0) return null

  return (
    <Collapsible title="killed" meta={`${killed.length}`}>
      <ul className="space-y-2">
        {killed.map((k) => {
          // Reason files lead with "# Killed <timestamp>" — drop that heading.
          const reason = k.reason
            .split("\n")
            .filter((l) => !l.startsWith("#") && l.trim())
            .join(" ")
            .trim()
          return (
            <li key={k.name} className="border-b border-border pb-2 last:border-0 last:pb-0">
              <div className="font-mono text-xs text-text">{k.name}</div>
              <p className="line-clamp-2 text-sm text-text-label">
                {reason || "no reason recorded"}
              </p>
            </li>
          )
        })}
      </ul>
    </Collapsible>
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
