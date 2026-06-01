import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
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
import { KanbanColumn } from "@/components/brand/kanban-column"
import { VideoCard } from "@/components/brand/video-card"
import { usePipeline, useHorizontalSlice, useCreateVideo } from "@/hooks/useBrand"
import { toast } from "@/lib/toast-store"

export function Brand() {
  const pipeline = usePipeline()
  const [newOpen, setNewOpen] = useState(false)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">brand</h1>
        <Button onClick={() => setNewOpen(true)}>+ new video</Button>
      </div>

      <Tabs defaultValue="pipeline">
        <TabsList>
          <TabsTrigger value="pipeline">pipeline</TabsTrigger>
          <TabsTrigger value="concepts">all concepts</TabsTrigger>
          <TabsTrigger value="scripts">all scripts</TabsTrigger>
          <TabsTrigger value="shotlists">all shot lists</TabsTrigger>
          <TabsTrigger value="titles">all titles</TabsTrigger>
          <TabsTrigger value="posting">all posting plans</TabsTrigger>
          <TabsTrigger value="performance">performance</TabsTrigger>
        </TabsList>

        {/* 1. Pipeline (kanban) */}
        <TabsContent value="pipeline">
          {pipeline.isLoading ? (
            <Skeleton className="h-72" />
          ) : pipeline.isError ? (
            <Panel title="error" statusDotColor="danger">
              <p className="text-text-secondary">could not load pipeline. backend on :8000?</p>
            </Panel>
          ) : (
            <div className="flex gap-3 overflow-x-auto pb-2">
              {(pipeline.data?.stages ?? []).map((stage, stageIdx) => {
                const cards = pipeline.data?.by_stage[stage] ?? []
                const isLast = stageIdx === (pipeline.data?.stages.length ?? 0) - 1
                return (
                  <KanbanColumn key={stage} stage={stage} count={cards.length}>
                    {cards.map((v) => (
                      <VideoCard
                        key={v.name}
                        video={v}
                        onAdvance={
                          isLast
                            ? undefined
                            : () =>
                                toast.show("stage-move endpoint pending (backend phase)", {
                                  detail: `${v.title} → next stage`,
                                })
                        }
                      />
                    ))}
                  </KanbanColumn>
                )
              })}
            </div>
          )}
        </TabsContent>

        {/* 2-6. Horizontal slices */}
        <TabsContent value="concepts">
          <SliceView section="concept" />
        </TabsContent>
        <TabsContent value="scripts">
          <SliceView section="script" />
        </TabsContent>
        <TabsContent value="shotlists">
          <SliceView section="shot_list" />
        </TabsContent>
        <TabsContent value="titles">
          <SliceView section="titles" />
        </TabsContent>
        <TabsContent value="posting">
          <SliceView section="posting_plan" />
        </TabsContent>
        <TabsContent value="performance">
          <SliceView section="performance" />
        </TabsContent>
      </Tabs>

      <NewVideoDialog open={newOpen} onOpenChange={setNewOpen} />
    </div>
  )
}

function SliceView({ section }: { section: string }) {
  const { data, isLoading, isError } = useHorizontalSlice(section)

  if (isLoading) return <Skeleton className="h-40" />
  if (isError)
    return (
      <Panel title="error" statusDotColor="danger">
        <p className="text-text-secondary">could not load {section}.</p>
      </Panel>
    )

  const videos = (data?.videos ?? []).filter((v) => v.content.trim())

  return (
    <div className="space-y-3">
      {videos.length === 0 ? (
        <Panel title={data?.title ?? section} meta="0 with content">
          <p className="text-sm text-text-label">no {section} content across videos yet</p>
        </Panel>
      ) : (
        videos.map((v) => (
          <Panel key={v.name} title={v.title} meta={v.stage.toLowerCase()} statusDotColor="accent">
            <pre className="whitespace-pre-wrap font-mono text-xs text-text-secondary">
              {v.content}
            </pre>
          </Panel>
        ))
      )}
    </div>
  )
}

function NewVideoDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const create = useCreateVideo()
  const [title, setTitle] = useState("")
  const [platform, setPlatform] = useState("YouTube")
  const [concept, setConcept] = useState("")

  function reset() {
    setTitle("")
    setPlatform("YouTube")
    setConcept("")
  }

  function submit() {
    const t = title.trim()
    if (!t) return
    create.mutate(
      { title: t, platform, concept: concept.trim() },
      {
        onSuccess: (r) => {
          toast.success("video created", r.name)
          onOpenChange(false)
          reset()
        },
        onError: (e) => toast.error("could not create video", String(e)),
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
          <DialogTitle>new video</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <div className="label mb-1">title</div>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="video title" />
          </div>
          <div>
            <div className="label mb-1">platform</div>
            <Select value={platform} onValueChange={setPlatform}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="YouTube">youtube</SelectItem>
                <SelectItem value="IG">instagram</SelectItem>
                <SelectItem value="TikTok">tiktok</SelectItem>
                <SelectItem value="multi">multi</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <div className="label mb-1">concept (one-liner)</div>
            <Textarea value={concept} onChange={(e) => setConcept(e.target.value)} rows={3} placeholder="the hook in one line..." />
          </div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            cancel
          </Button>
          <Button onClick={submit} disabled={!title.trim() || create.isPending}>
            create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
