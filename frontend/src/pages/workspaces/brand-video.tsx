import { useState } from "react"
import { Link, useParams } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Tag } from "@/components/ui/tag"
import { SkillButton } from "@/components/ui/skill-button"
import {
  useVideoWorkspace,
  useRunBrandSkill,
  type VideoSection,
} from "@/hooks/useBrand"
import { toast } from "@/lib/toast-store"

/** Section filename → the brand skill that generates it (+ button label). */
const SECTION_SKILL: Record<string, { skill: string; label: string }> = {
  "01_Concept.md": { skill: "generate_hook_variants", label: "generate hooks" },
  "02_Script.md": { skill: "draft_first_pass_script", label: "draft first-pass script" },
  "03_Shot_List.md": { skill: "generate_shot_list", label: "generate shot list" },
  "06_Titles.md": { skill: "generate_title_variants", label: "generate title variants" },
  "07_Description_Tags.md": { skill: "generate_description_tags", label: "generate description + tags" },
  "08_Thumbnail_Copy.md": { skill: "generate_thumbnail_copy", label: "generate thumbnail copy" },
}

export function BrandVideo() {
  const { id } = useParams<{ id: string }>()
  const name = id ? decodeURIComponent(id) : undefined
  const { data, isLoading, isError } = useVideoWorkspace(name)
  const runSkill = useRunBrandSkill(name)

  return (
    <div className="min-h-screen bg-bg text-text p-6">
      <div className="mx-auto max-w-[1100px] space-y-5">
        <div className="flex items-center justify-between">
          <Link to="/brand" className="font-mono text-xs text-text-secondary hover:text-accent">
            ← brand
          </Link>
          {name && <span className="font-mono text-xs text-text-label">{name}</span>}
        </div>

        {isError && (
          <Panel title="error" statusDotColor="danger">
            <p className="text-text-secondary">could not load video “{name}”.</p>
          </Panel>
        )}
        {isLoading && (
          <div className="space-y-4">
            <Skeleton className="h-16" />
            <Skeleton className="h-40" />
          </div>
        )}

        {data && name && (
          <>
            {/* 1. Header */}
            <div className="flex flex-wrap items-end justify-between gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">{data.status.title}</h1>
              <div className="flex flex-wrap items-center gap-2">
                <Tag variant="accent">{data.status.stage?.toLowerCase() || "ideas"}</Tag>
                <Tag variant="muted">{data.status.platform || "—"}</Tag>
                {data.status.posting_date && (
                  <span className="font-mono text-xs text-text-secondary">
                    posts {data.status.posting_date}
                  </span>
                )}
              </div>
            </div>

            {/* 2-10. Sections (skills attach per section) */}
            <div className="space-y-3">
              {data.sections.map((s) => (
                <SectionPanel
                  key={s.filename}
                  section={s}
                  onRunSkill={(skill) => runSkill.mutateAsync({ skill })}
                />
              ))}
            </div>

            {/* 11. Ask Claude */}
            <AskClaudeSection
              onAsk={(question) => runSkill.mutateAsync({ skill: "ask_claude_about_video", question })}
            />
          </>
        )}
      </div>
    </div>
  )
}

function SectionPanel({
  section,
  onRunSkill,
}: {
  section: VideoSection
  onRunSkill: (skill: string) => Promise<{ run_id?: string }>
}) {
  const mapped = SECTION_SKILL[section.filename]
  const isTranscript = section.filename.startsWith("05_")

  return (
    <Panel title={section.title} statusDotColor={section.content.trim() ? "accent" : "muted"}>
      {isTranscript ? (
        <p className="text-sm text-text-label">
          transcript + cut suggestions — deferred (needs local whisper, phase 13.5)
        </p>
      ) : section.content.trim() ? (
        <pre className="whitespace-pre-wrap font-mono text-xs text-text-secondary">
          {section.content}
        </pre>
      ) : (
        <p className="text-sm text-text-label">empty</p>
      )}
      {mapped && (
        <div className="mt-3">
          <SkillButton onRun={() => onRunSkill(mapped.skill)}>{mapped.label}</SkillButton>
        </div>
      )}
    </Panel>
  )
}

function AskClaudeSection({
  onAsk,
}: {
  onAsk: (question: string) => Promise<{ run_id?: string }>
}) {
  const [q, setQ] = useState("")
  const [pending, setPending] = useState(false)

  async function ask() {
    const question = q.trim()
    if (!question) return
    setPending(true)
    try {
      const r = await onAsk(question)
      setQ("")
      toast.success("started in background — see background runs", r?.run_id)
    } catch (e) {
      toast.error("failed to start", String(e))
    } finally {
      setPending(false)
    }
  }

  return (
    <Panel title="ask claude about this video" statusDotColor="accent">
      <Textarea value={q} onChange={(e) => setQ(e.target.value)} rows={3} placeholder="what do you want help with on this video?" />
      <div className="mt-2 flex justify-end">
        <Button onClick={ask} disabled={!q.trim() || pending}>
          ask claude
        </Button>
      </div>
    </Panel>
  )
}
