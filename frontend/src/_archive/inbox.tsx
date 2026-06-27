import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
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
import { useInbox, useInboxAction, type InboxItem } from "@/hooks/useInbox"
import { useProjects } from "@/hooks/useProjects"
import { TASK_SECTIONS } from "@/hooks/useTasks"
import { openInOs } from "@/lib/open-in-os"
import { toast } from "@/lib/toast-store"

export function Inbox() {
  const { data, isLoading, isError } = useInbox()

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">inbox</h1>

      {isError && (
        <Panel title="error" statusDotColor="danger">
          <p className="text-text-secondary">
            could not load inbox. is the backend running on :8000?
          </p>
        </Panel>
      )}

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      )}

      {data && data.length === 0 && (
        <Panel title="inbox" meta="0 items">
          <p className="text-text-secondary">inbox zero. nothing to triage.</p>
        </Panel>
      )}

      {data && data.length > 0 && (
        <div className="space-y-3">
          {data.map((item) => (
            <InboxItemPanel key={item.filename} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}

function InboxItemPanel({ item }: { item: InboxItem }) {
  const action = useInboxAction()
  const { data: projects } = useProjects()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [convertOpen, setConvertOpen] = useState(false)

  const date = item.mtime?.slice(0, 16).replace("T", " ") ?? ""

  function run(req: Parameters<typeof action.mutate>[0]["req"], label: string) {
    action.mutate(
      { filename: item.filename, req },
      {
        onSuccess: () => toast.success(label, item.filename),
        onError: (e) => toast.error(`could not ${label}`, String(e)),
      },
    )
  }

  return (
    <Panel title={item.filename} meta={date}>
      <p className="mb-3 whitespace-pre-wrap text-sm text-text-secondary line-clamp-4">
        {item.preview.slice(0, 300)}
        {item.preview.length > 300 ? "…" : ""}
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => openInOs(item.filename)}
        >
          open in os
        </Button>

        <Select
          onValueChange={(projectId) =>
            run({ action: "move", project_id: projectId }, "move to project")
          }
        >
          <SelectTrigger className="h-7 w-44 text-xs">
            <SelectValue placeholder="move to project..." />
          </SelectTrigger>
          <SelectContent>
            {(projects ?? []).map((p) => (
              <SelectItem key={p.id} value={p.id}>
                {p.id} {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => setConvertOpen(true)}
        >
          convert to task
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => run({ action: "archive" }, "archive")}
        >
          archive
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="text-danger hover:text-danger"
          onClick={() => setConfirmDelete(true)}
        >
          delete
        </Button>
      </div>

      <ConvertToTaskDialog
        open={convertOpen}
        onOpenChange={setConvertOpen}
        defaultTitle={item.filename.replace(/\.md$/, "")}
        onConfirm={(section, title) => {
          run(
            { action: "convert_to_task", section, title },
            "convert to task",
          )
          setConvertOpen(false)
        }}
      />

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>delete item</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-text-secondary">
            permanently delete{" "}
            <span className="font-mono text-text">{item.filename}</span>? this
            cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
              cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                run({ action: "delete" }, "delete")
                setConfirmDelete(false)
              }}
            >
              delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Panel>
  )
}

function ConvertToTaskDialog({
  open,
  onOpenChange,
  defaultTitle,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  defaultTitle: string
  onConfirm: (section: string, title: string) => void
}) {
  const [section, setSection] = useState<string>("This week")
  const [title, setTitle] = useState(defaultTitle)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>convert to task</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <div className="label mb-1">title</div>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <div className="label mb-1">section</div>
            <Select value={section} onValueChange={setSection}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TASK_SECTIONS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            cancel
          </Button>
          <Button
            onClick={() => onConfirm(section, title.trim() || defaultTitle)}
            disabled={!title.trim()}
          >
            convert
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
