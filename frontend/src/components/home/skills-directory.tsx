import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Collapsible } from "@/components/ui/collapsible"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusDot, type StatusColor } from "@/components/ui/status-dot"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useSkillsStatus, type SkillStatus } from "@/hooks/useHome"
import { useRunSkill } from "@/hooks/useSkills"
import { countdownLabel } from "@/lib/status"
import { toast } from "@/lib/toast-store"

const DOT: Record<SkillStatus["status"], StatusColor> = {
  ok: "success",
  due: "warning",
  failed: "danger",
  never: "muted",
}

const STATUS_TEXT: Record<SkillStatus["status"], string> = {
  ok: "healthy",
  due: "due",
  failed: "failed last run",
  never: "never run",
}

/**
 * GROUND §3c — Skills & Agents directory (Option 3: list + status + last run).
 * 🟢 run recently · 🟡 due · 🔴 failed last run · ⚪ never run.
 * [run] launches the skill in the background (Background_Runs page tracks it);
 * skills that need richer inputs link to the page that owns them. Collapsed by
 * default on mobile (accordion), open on desktop.
 */
export function SkillsAgentsDirectory() {
  const { data, isLoading } = useSkillsStatus()
  // Evaluated once at mount: desktop starts open, mobile starts collapsed.
  const [defaultOpen] = useState(() => window.matchMedia("(min-width: 768px)").matches)

  return (
    <Collapsible
      title="skills & agents"
      meta={data ? `${data.skills.length} registered` : undefined}
      defaultOpen={defaultOpen}
    >
      {isLoading ? (
        <Skeleton className="h-32" />
      ) : !data || data.skills.length === 0 ? (
        <p className="text-sm text-text-label">no skills registered</p>
      ) : (
        <div className="space-y-0.5">
          {data.skills.map((s) => (
            <SkillRow key={s.key} skill={s} />
          ))}
        </div>
      )}
    </Collapsible>
  )
}

function lastRunLabel(s: SkillStatus): string {
  if (s.status === "never") return s.note ?? "never run"
  const rel = s.last_run_at ? countdownLabel(s.last_run_at.slice(0, 10)) : null
  const when = rel === "today" ? "today" : rel ?? "—"
  return s.status === "failed" ? `failed ${when}` : `last run ${when}`
}

function SkillRow({ skill }: { skill: SkillStatus }) {
  const runSkill = useRunSkill()
  const navigate = useNavigate()
  const [promptOpen, setPromptOpen] = useState(false)
  const [promptValue, setPromptValue] = useState("")

  function launch(args?: Record<string, unknown>) {
    if (!skill.run_skill) return
    runSkill.mutate(
      { skill: skill.run_skill, args, label: skill.label },
      {
        onSuccess: (r) => toast.success("started in background — see background runs", r.run_id),
        onError: (e) => toast.error("failed to start", String(e)),
      },
    )
  }

  function onRun() {
    if (skill.run_skill && skill.prompt_arg) {
      setPromptOpen(true)
    } else if (skill.run_skill) {
      launch()
    } else if (skill.run_target) {
      navigate(skill.run_target)
    }
  }

  const runnable = Boolean(skill.run_skill || skill.run_target)

  return (
    <div className="flex items-center gap-2 rounded-sm px-1 py-1.5 hover:bg-bg-panel-hover">
      <StatusDot color={DOT[skill.status]} />
      <span className="min-w-0 flex-1 truncate text-sm text-text">{skill.label}</span>
      <span
        className="hidden shrink-0 font-mono text-xs text-text-secondary sm:inline"
        title={STATUS_TEXT[skill.status]}
      >
        {lastRunLabel(skill)}
      </span>
      <Button
        variant="ghost"
        size="sm"
        onClick={onRun}
        disabled={!runnable || runSkill.isPending}
        title={!runnable ? skill.note ?? "not runnable" : skill.run_target ? "open" : "run"}
      >
        {skill.run_target && !skill.run_skill ? "open" : "run"}
      </Button>

      {skill.prompt_arg && (
        <Dialog
          open={promptOpen}
          onOpenChange={(o) => {
            setPromptOpen(o)
            if (!o) setPromptValue("")
          }}
        >
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>{skill.label.toLowerCase()}</DialogTitle>
            </DialogHeader>
            <div className="label mb-1">{skill.prompt_arg.replace(/_/g, " ")}</div>
            {skill.prompt_arg === "ticker" ? (
              <Input
                value={promptValue}
                onChange={(e) => setPromptValue(e.target.value)}
                placeholder="e.g. ASML"
                mono
              />
            ) : (
              <Textarea
                value={promptValue}
                onChange={(e) => setPromptValue(e.target.value)}
                placeholder="describe it…"
                rows={4}
              />
            )}
            <DialogFooter>
              <Button variant="secondary" onClick={() => setPromptOpen(false)}>
                cancel
              </Button>
              <Button
                disabled={!promptValue.trim()}
                onClick={() => {
                  launch({ [skill.prompt_arg as string]: promptValue.trim() })
                  setPromptOpen(false)
                  setPromptValue("")
                }}
              >
                run
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
