import { useState } from "react"
import { ExternalLink } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Tag } from "@/components/ui/tag"
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
import {
  usePipeline,
  useHorizontalSlice,
  useCreateVideo,
  useMoveStage,
  usePostingLog,
  useInspirations,
  useRequestEdit,
  type PostingRow,
} from "@/hooks/useBrand"
import { toast } from "@/lib/toast-store"

export function Brand() {
  const pipeline = usePipeline()
  const moveStage = useMoveStage()
  const [newOpen, setNewOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)

  function move(name: string, stage?: string) {
    moveStage.mutate(
      { name, stage },
      { onError: (e) => toast.error("could not move card", String(e)) },
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">brand</h1>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => setEditOpen(true)}>
            + new edit
          </Button>
          <Button onClick={() => setNewOpen(true)}>+ new video</Button>
        </div>
      </div>

      <Tabs defaultValue="pipeline">
        <TabsList>
          <TabsTrigger value="pipeline">pipeline</TabsTrigger>
          <TabsTrigger value="inspirations">inspirations</TabsTrigger>
          <TabsTrigger value="posting">posting log</TabsTrigger>
          <TabsTrigger value="concepts">all concepts</TabsTrigger>
          <TabsTrigger value="scripts">all scripts</TabsTrigger>
          <TabsTrigger value="shotlists">all shot lists</TabsTrigger>
          <TabsTrigger value="titles">all titles</TabsTrigger>
          <TabsTrigger value="postingplans">all posting plans</TabsTrigger>
          <TabsTrigger value="performance">performance</TabsTrigger>
        </TabsList>

        {/* 1. Pipeline (kanban) — cards move between stages */}
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
                const stages = pipeline.data?.stages ?? []
                const isLast = stageIdx === stages.length - 1
                return (
                  <KanbanColumn key={stage} stage={stage} count={cards.length}>
                    {cards.map((v) => (
                      <VideoCard
                        key={v.name}
                        video={v}
                        stages={stages}
                        onMove={(s) => move(v.name, s)}
                        onAdvance={isLast ? undefined : () => move(v.name)}
                        busy={moveStage.isPending && moveStage.variables?.name === v.name}
                      />
                    ))}
                  </KanbanColumn>
                )
              })}
            </div>
          )}
        </TabsContent>

        {/* 2. Inspirations board */}
        <TabsContent value="inspirations">
          <InspirationsView />
        </TabsContent>

        {/* 3. Posting log / calendar */}
        <TabsContent value="posting">
          <PostingView />
        </TabsContent>

        {/* 4-9. Horizontal slices */}
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
        <TabsContent value="postingplans">
          <SliceView section="posting_plan" />
        </TabsContent>
        <TabsContent value="performance">
          <SliceView section="performance" />
        </TabsContent>
      </Tabs>

      <NewVideoDialog open={newOpen} onOpenChange={setNewOpen} />
      <NewEditDialog open={editOpen} onOpenChange={setEditOpen} />
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

function InspirationsView() {
  const { data, isLoading, isError } = useInspirations()

  if (isLoading) return <Skeleton className="h-40" />
  if (isError)
    return (
      <Panel title="error" statusDotColor="danger">
        <p className="text-text-secondary">could not load inspirations.</p>
      </Panel>
    )

  const items = data?.inspirations ?? []

  return (
    <div className="space-y-3">
      <p className="text-xs text-text-label">
        reference reels + craft notes from <code>02_Inspirations/</code>. add your own as
        markdown notes there — voice &amp; creative direction stay yours (miro / onenote).
      </p>
      {items.length === 0 ? (
        <Panel title="inspirations" meta="empty">
          <p className="text-sm text-text-label">no inspiration notes yet.</p>
        </Panel>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {items.map((ins) => (
            <Panel
              key={ins.name}
              title={ins.title}
              meta={ins.platform || undefined}
              statusDotColor="accent"
            >
              <div className="space-y-2">
                {ins.url && ins.url !== "https://..." && (
                  <a
                    href={ins.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 font-mono text-xs text-accent hover:underline"
                  >
                    open reference <ExternalLink className="h-3 w-3" />
                  </a>
                )}
                {ins.notes && (
                  <pre className="whitespace-pre-wrap font-mono text-xs text-text-secondary">
                    {ins.notes}
                  </pre>
                )}
                {ins.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {ins.tags.map((t) => (
                      <Tag key={t} variant="muted">
                        {t}
                      </Tag>
                    ))}
                  </div>
                )}
              </div>
            </Panel>
          ))}
        </div>
      )}
    </div>
  )
}

function PostingRowList({ rows, empty }: { rows: PostingRow[]; empty: string }) {
  if (rows.length === 0)
    return <p className="text-sm text-text-label">{empty}</p>
  return (
    <div className="space-y-1.5">
      {rows.map((r) => (
        <a
          key={r.name}
          href={`/workspace/brand/${encodeURIComponent(r.name)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-between gap-3 rounded-sm border border-border px-3 py-2 hover:border-accent-dim"
        >
          <span className="truncate text-sm text-text">{r.title}</span>
          <span className="flex shrink-0 items-center gap-3 font-mono text-[11px] text-text-label">
            <span>{r.platform || "—"}</span>
            <span>{r.stage.toLowerCase()}</span>
            <span className="text-text-secondary">{r.posting_date || "no date"}</span>
          </span>
        </a>
      ))}
    </div>
  )
}

function PostingView() {
  const { data, isLoading, isError } = usePostingLog()

  if (isLoading) return <Skeleton className="h-40" />
  if (isError)
    return (
      <Panel title="error" statusDotColor="danger">
        <p className="text-text-secondary">could not load posting log.</p>
      </Panel>
    )

  return (
    <div className="space-y-3">
      <Panel title="scheduled" meta={`${data?.scheduled.length ?? 0}`} statusDotColor="accent">
        <PostingRowList rows={data?.scheduled ?? []} empty="nothing scheduled — set a posting date on a video's posting plan" />
      </Panel>
      <Panel title="published" meta={`${data?.published.length ?? 0}`}>
        <PostingRowList rows={data?.published ?? []} empty="nothing published yet" />
      </Panel>
      <Panel title="in pipeline · no date" meta={`${data?.undated.length ?? 0}`}>
        <PostingRowList rows={data?.undated ?? []} empty="—" />
      </Panel>
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

/** "New edit" — stub trigger for the future Remotion edit repo (no real edit). */
function NewEditDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const pipeline = usePipeline()
  const requestEdit = useRequestEdit()
  const [videoName, setVideoName] = useState("")
  const [note, setNote] = useState("")

  const videos = pipeline.data
    ? Object.values(pipeline.data.by_stage).flat()
    : []

  function reset() {
    setVideoName("")
    setNote("")
  }

  function submit() {
    requestEdit.mutate(
      { video_name: videoName || null, note: note.trim() || null },
      {
        onSuccess: (r) => {
          toast.show("edit queued — remotion repo not yet connected (stub)", {
            detail: r.message,
          })
          onOpenChange(false)
          reset()
        },
        onError: (e) => toast.error("could not queue edit", String(e)),
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
          <DialogTitle>new edit (stub)</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <p className="text-xs text-text-label">
            triggers the future remotion edit repo. not wired yet — this just queues the
            request to <code>05_Edits/_Edit_Queue.md</code>.
          </p>
          <div>
            <div className="label mb-1">video (optional)</div>
            <Select value={videoName || "none"} onValueChange={(v) => setVideoName(v === "none" ? "" : v)}>
              <SelectTrigger>
                <SelectValue placeholder="unassigned" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">unassigned</SelectItem>
                {videos.map((v) => (
                  <SelectItem key={v.name} value={v.name}>
                    {v.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <div className="label mb-1">note (optional)</div>
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} placeholder="what the edit should do..." />
          </div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            cancel
          </Button>
          <Button onClick={submit} disabled={requestEdit.isPending}>
            queue edit
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
