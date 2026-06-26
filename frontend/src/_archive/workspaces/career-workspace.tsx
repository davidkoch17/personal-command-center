import { useState } from "react"
import { Link } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { CountdownDisplay } from "@/components/ui/countdown-display"
import { ChecklistItem } from "@/components/ui/checklist-item"
import { SkillButton } from "@/components/ui/skill-button"
import { InfoBarrierBanner } from "@/components/ui/info-barrier-banner"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  useCareerWorkspace,
  useCareerModel,
  useToggleChecklist,
  useRunCareerSkill,
  type ChecklistEntry,
} from "@/hooks/useCareer"
import { formatBoth } from "@/lib/dates"
import { useRunSkill } from "@/hooks/useSkills"
import { useInfoBarrierActive } from "@/hooks/useSystem"
import { openInOs } from "@/lib/open-in-os"
import { toast } from "@/lib/toast-store"

export function CareerWorkspace() {
  const ws = useCareerWorkspace()
  const toggle = useToggleChecklist()
  const careerSkill = useRunCareerSkill()
  const askSkill = useRunSkill()
  const barrier = useInfoBarrierActive()

  function toggleItem(checklist: "onboarding" | "technicals", index: number) {
    toggle.mutate(
      { checklist, index },
      { onError: (e) => toast.error("could not toggle", String(e)) },
    )
  }

  return (
    <div className="min-h-screen bg-bg text-text p-6">
      <div className="mx-auto max-w-[1100px] space-y-5">
        <div className="flex items-center justify-between">
          <Link to="/career" className="font-mono text-xs text-text-secondary hover:text-accent">
            ← career
          </Link>
        </div>

        {ws.isLoading && (
          <div className="space-y-4">
            <Skeleton className="h-20" />
            <Skeleton className="h-40" />
          </div>
        )}

        {ws.data && (
          <>
            <h1 className="text-2xl font-semibold tracking-tight">career workspace</h1>

            {/* 1. Countdown + critical dates */}
            <Panel title="countdown + critical dates" statusDotColor="accent">
              <CountdownDisplay date={ws.data.start_date} label="evercore start" />
            </Panel>

            {/* 2. Onboarding admin checklist */}
            <Panel
              title="onboarding admin checklist"
              meta={`${ws.data.onboarding_done}/${ws.data.onboarding_total}`}
              statusDotColor="success"
            >
              <ChecklistGroup
                items={ws.data.onboarding}
                disabled={toggle.isPending}
                onToggle={(i) => toggleItem("onboarding", i)}
              />
            </Panel>

            {/* 3. Technicals refresh tracker */}
            <Panel
              title="technicals refresh tracker"
              meta={`${ws.data.technicals_done}/${ws.data.technicals_total}`}
              statusDotColor="accent"
            >
              {ws.data.technicals.length === 0 ? (
                <p className="text-sm text-text-label">no technicals modules in vault</p>
              ) : (
                <div className="space-y-1">
                  {ws.data.technicals.map((item, i) => (
                    <div key={i} className="flex items-center justify-between gap-2">
                      <ChecklistItem
                        checked={item.checked}
                        disabled={toggle.isPending}
                        onToggle={() => toggleItem("technicals", i)}
                      >
                        {item.text}
                      </ChecklistItem>
                      <SkillButton
                        size="sm"
                        variant="ghost"
                        onRun={() => careerSkill.mutateAsync({ skill: "quiz_technicals", arg: item.text })}
                      >
                        quiz me
                      </SkillButton>
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            {/* Skills */}
            <SkillsPanel />

            {/* 4. 3-statement model */}
            <ModelStatusPanel />

            {/* 5. First 90 days (editable, local) */}
            <EditablePanel
              title="first 90 days plan"
              placeholder="goals · learning · meetings · what not to do..."
            />

            {/* 6. Deal pipeline (info-barrier) */}
            <Panel title="deal pipeline" statusDotColor={barrier ? "warning" : "muted"}>
              <InfoBarrierBanner message="sector / title only — no deal specifics" className="mb-3" />
              {barrier ? (
                <p className="text-sm text-text-secondary">
                  info barrier active — log deals by sector + title only, no specifics.
                </p>
              ) : (
                <p className="text-sm text-text-label">
                  activates at evercore start (or when forced on in settings).
                </p>
              )}
            </Panel>

            {/* 7. Mentor / network */}
            <EditablePanel title="mentor / network plan" placeholder="who to build with at evercore · outreach status..." />

            {/* 8. Career strategy long-term */}
            <Panel title="career strategy (long-term)" statusDotColor="muted">
              <p className="text-sm text-text-label">
                strategy docs live in 3_Career/04_Career_Strategy/ — file-surfacing endpoint pending.
              </p>
            </Panel>

            {/* 9. Documents / files */}
            <Panel title="documents / files" statusDotColor="muted">
              <div className="flex flex-wrap gap-2">
                {["Contract.pdf", "CV_current.pdf", "Zeugnisse.pdf"].map((f) => (
                  <Button key={f} variant="secondary" size="sm" onClick={() => openInOs(`3_Career/${f}`)}>
                    {f}
                  </Button>
                ))}
              </div>
              <p className="mt-2 text-xs text-text-label">
                key-file list is a placeholder until a career key-files endpoint lands.
              </p>
            </Panel>

            {/* 10. Ask Claude */}
            <AskCareerSection
              onAsk={(question) => askSkill.mutateAsync({ skill: "ask_anything", args: { question: `About my career: ${question}` }, label: "Ask career" })}
            />
          </>
        )}
      </div>
    </div>
  )
}

function ChecklistGroup({
  items,
  disabled,
  onToggle,
}: {
  items: ChecklistEntry[]
  disabled: boolean
  onToggle: (index: number) => void
}) {
  if (items.length === 0)
    return <p className="text-sm text-text-label">no items in vault</p>
  return (
    <div className="space-y-0.5">
      {items.map((item, i) => (
        <ChecklistItem key={i} checked={item.checked} disabled={disabled} onToggle={() => onToggle(i)}>
          {item.text}
        </ChecklistItem>
      ))}
    </div>
  )
}

// Skills row: mock interview + arg-based skills via dialogs
function SkillsPanel() {
  const careerSkill = useRunCareerSkill()
  const [dialog, setDialog] = useState<null | "deal_note" | "model_checker" | "industry_primer" | "career_letter_draft">(null)

  function started(runId?: string) {
    toast.success("started in background — see background runs", runId)
  }

  return (
    <Panel title="skills" statusDotColor="accent">
      <div className="flex flex-wrap gap-2">
        <SkillButton onRun={() => careerSkill.mutateAsync({ skill: "mock_interview", arg: "technical" })}>
          mock interview (technical)
        </SkillButton>
        <SkillButton onRun={() => careerSkill.mutateAsync({ skill: "mock_interview", arg: "behavioral" })}>
          mock interview (behavioral)
        </SkillButton>
        <Button size="sm" variant="secondary" onClick={() => setDialog("deal_note")}>
          deal note
        </Button>
        <Button size="sm" variant="secondary" onClick={() => setDialog("model_checker")}>
          model checker
        </Button>
        <Button size="sm" variant="secondary" onClick={() => setDialog("industry_primer")}>
          industry primer
        </Button>
        <Button size="sm" variant="secondary" onClick={() => setDialog("career_letter_draft")}>
          career letter draft
        </Button>
      </div>

      <SkillArgDialog
        open={dialog === "deal_note"}
        onOpenChange={(o) => setDialog(o ? "deal_note" : null)}
        title="deal note"
        fieldA={{ label: "paste article text", multiline: true }}
        onSubmit={(a) =>
          careerSkill.mutate(
            { skill: "deal_note", arg: a },
            { onSuccess: (r) => started(r.run_id), onError: (e) => toast.error("failed", String(e)) },
          )
        }
      />
      <SkillArgDialog
        open={dialog === "model_checker"}
        onOpenChange={(o) => setDialog(o ? "model_checker" : null)}
        title="model checker"
        fieldA={{ label: "model summary", multiline: true }}
        onSubmit={(a) =>
          careerSkill.mutate(
            { skill: "model_checker", arg: a },
            { onSuccess: (r) => started(r.run_id), onError: (e) => toast.error("failed", String(e)) },
          )
        }
      />
      <SkillArgDialog
        open={dialog === "industry_primer"}
        onOpenChange={(o) => setDialog(o ? "industry_primer" : null)}
        title="industry primer"
        fieldA={{ label: "sector", multiline: false }}
        onSubmit={(a) =>
          careerSkill.mutate(
            { skill: "industry_primer", arg: a },
            { onSuccess: (r) => started(r.run_id), onError: (e) => toast.error("failed", String(e)) },
          )
        }
      />
      <SkillArgDialog
        open={dialog === "career_letter_draft"}
        onOpenChange={(o) => setDialog(o ? "career_letter_draft" : null)}
        title="career letter draft"
        fieldA={{ label: "kind (cover / outreach / thank-you)", multiline: false }}
        fieldB={{ label: "context", multiline: true }}
        onSubmit={(a, b) =>
          careerSkill.mutate(
            { skill: "career_letter_draft", arg: a, context: b },
            { onSuccess: (r) => started(r.run_id), onError: (e) => toast.error("failed", String(e)) },
          )
        }
      />
    </Panel>
  )
}

// 3-statement model status — detects the Cowork-built workbook in 05_Current_Job.
function ModelStatusPanel() {
  const model = useCareerModel()
  const ready = model.data?.status === "ready"
  return (
    <Panel
      title="3-statement model status"
      statusDotColor={model.isLoading ? "muted" : ready ? "success" : "warning"}
    >
      {model.isLoading ? (
        <Skeleton className="h-10" />
      ) : ready ? (
        <div className="space-y-1">
          <Button variant="secondary" size="sm" onClick={() => model.data?.path && openInOs(model.data.path)}>
            open {model.data?.name} ↗
          </Button>
          <p className="text-xs text-text-label">
            last modified {formatBoth(model.data!.last_modified!)} · {model.data?.path}
          </p>
        </div>
      ) : (
        <div className="space-y-1">
          <p className="text-sm text-text-label">
            not started — build in Cowork, then save the workbook to{" "}
            <span className="font-mono">{model.data?.expected_path}</span> to track it here.
          </p>
          <p className="text-xs text-text-label">
            use “model checker” above to review a model summary in the meantime.
          </p>
        </div>
      )}
    </Panel>
  )
}

function EditablePanel({ title, placeholder }: { title: string; placeholder: string }) {
  const [text, setText] = useState("")
  return (
    <Panel title={title} statusDotColor="muted">
      <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} placeholder={placeholder} />
      <p className="mt-1 text-xs text-text-label">persistence pending (backend phase)</p>
    </Panel>
  )
}

function AskCareerSection({
  onAsk,
}: {
  onAsk: (q: string) => Promise<{ run_id?: string }>
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
    <Panel title="ask claude about my career" statusDotColor="accent">
      <Textarea value={q} onChange={(e) => setQ(e.target.value)} rows={3} placeholder="career question — loads personal_memory + career files as context..." />
      <div className="mt-2 flex justify-end">
        <Button onClick={ask} disabled={!q.trim() || pending}>
          ask claude
        </Button>
      </div>
    </Panel>
  )
}

function SkillArgDialog({
  open,
  onOpenChange,
  title,
  fieldA,
  fieldB,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  fieldA: { label: string; multiline: boolean }
  fieldB?: { label: string; multiline: boolean }
  onSubmit: (a: string, b: string) => void
}) {
  const [a, setA] = useState("")
  const [b, setB] = useState("")
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o)
        if (!o) {
          setA("")
          setB("")
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <div className="label mb-1">{fieldA.label}</div>
            {fieldA.multiline ? (
              <Textarea value={a} onChange={(e) => setA(e.target.value)} rows={4} />
            ) : (
              <Input value={a} onChange={(e) => setA(e.target.value)} />
            )}
          </div>
          {fieldB && (
            <div>
              <div className="label mb-1">{fieldB.label}</div>
              {fieldB.multiline ? (
                <Textarea value={b} onChange={(e) => setB(e.target.value)} rows={4} />
              ) : (
                <Input value={b} onChange={(e) => setB(e.target.value)} />
              )}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            cancel
          </Button>
          <Button
            disabled={!a.trim() || (!!fieldB && !b.trim())}
            onClick={() => {
              onSubmit(a.trim(), b.trim())
              onOpenChange(false)
              setA("")
              setB("")
            }}
          >
            run
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
