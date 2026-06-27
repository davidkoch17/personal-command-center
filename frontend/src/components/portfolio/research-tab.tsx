import { useMemo, useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Tag } from "@/components/ui/tag"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { InlineMd } from "@/components/ui/inline-markdown"
import {
  useResearchSkills,
  useRunResearch,
  useReports,
  useHypotheses,
  type ReportSidecar,
} from "@/hooks/usePortfolioHub"
import { useRuns, isRunActive } from "@/hooks/useRuns"
import { DecisionLogPanel } from "./decision-log"
import { openInOs } from "@/lib/open-in-os"
import { toast } from "@/lib/toast-store"

export function ResearchTab() {
  return (
    <div className="space-y-5">
      <RunResearchLauncher />
      <ReportsLibrary />
      <div className="grid gap-5 lg:grid-cols-2">
        <HypothesisTracker />
        <DecisionLogPanel />
      </div>
    </div>
  )
}

function RunResearchLauncher() {
  const skills = useResearchSkills()
  const run = useRunResearch()
  const runs = useRuns()
  const [skill, setSkill] = useState("stock_analysis")
  const [target, setTarget] = useState("")

  const meta = skills.data?.skills.find((s) => s.key === skill)
  const needsTarget = meta ? meta.target_kind !== "none" : true
  const activeResearch = (runs.data?.runs ?? []).filter(
    (r) => isRunActive(r.status) && /analysis|earnings|sector|peer|valuation|macro|short|insider|13f|tracker/i.test(r.label ?? ""),
  )

  function launch() {
    if (needsTarget && !target.trim()) return
    run.mutate(
      { skill, target: target.trim() || undefined },
      {
        onSuccess: (r) => {
          toast.success("research queued", `${skill} ${r.target ?? ""} → background run`)
          setTarget("")
        },
        onError: (e) => toast.error("could not launch research", String(e)),
      },
    )
  }

  return (
    <Panel title="run research" statusDotColor="accent" meta="background job (same runner as idea validation)">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[12rem]">
          <div className="label mb-1">skill</div>
          <Select value={skill} onValueChange={setSkill}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {(skills.data?.skills ?? []).map((s) => (
                <SelectItem key={s.key} value={s.key}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="min-w-[10rem] flex-1">
          <div className="label mb-1">
            target {meta ? `(${meta.target_kind})` : ""}
          </div>
          <Input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            mono
            placeholder={needsTarget ? "NKE / semiconductors / fund" : "— none —"}
            disabled={!needsTarget}
          />
        </div>
        <Button onClick={launch} disabled={run.isPending || (needsTarget && !target.trim())}>
          {run.isPending ? "queuing…" : "run"}
        </Button>
      </div>

      {activeResearch.length > 0 && (
        <div className="mt-3 space-y-1 border-t border-border pt-3">
          {activeResearch.map((r) => (
            <div key={r.run_id} className="flex items-center gap-2 text-xs">
              <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-accent" />
              <span className="text-text-secondary">{r.label}</span>
              <span className="font-mono text-text-label">{r.status}</span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  )
}

function recVariant(rec?: string | null): "success" | "danger" | "warning" | "muted" {
  const r = (rec ?? "").toLowerCase()
  if (/(accumulate|buy|add|overweight|long)/.test(r)) return "success"
  if (/(trim|sell|short|avoid|underweight|reduce)/.test(r)) return "danger"
  if (/(hold|neutral|in line)/.test(r)) return "warning"
  return "muted"
}

function ReportsLibrary() {
  const { data, isLoading } = useReports()

  // Group reports by target/ticker, newest first within each.
  const groups = useMemo(() => {
    const map: Record<string, ReportSidecar[]> = {}
    for (const r of data?.reports ?? []) {
      const key = (r.ticker as string) || (r.target as string) || "—"
      ;(map[key] ??= []).push(r)
    }
    return Object.entries(map).sort((a, b) => a[0].localeCompare(b[0]))
  }, [data])

  return (
    <Panel
      title="reports library"
      meta={data ? `${data.count} reports` : undefined}
      statusDotColor="accent"
    >
      {isLoading ? (
        <Skeleton className="h-32" />
      ) : !groups.length ? (
        <p className="text-sm text-text-label">no reports yet. run a stock analysis above.</p>
      ) : (
        <div className="space-y-4">
          {groups.map(([key, reports]) => (
            <div key={key}>
              <div className="mb-1.5 flex items-baseline gap-2">
                <span className="font-mono text-sm text-text">{key}</span>
                <span className="text-xs text-text-label">{reports.length} report{reports.length > 1 ? "s" : ""}</span>
              </div>
              <ul className="space-y-1">
                {reports.map((r, i) => (
                  <li key={i} className="flex items-center gap-2 rounded-sm border border-border/60 px-2.5 py-1.5 text-sm">
                    <span className="font-mono text-xs text-text-label">{r.analysis_date}</span>
                    <span className="text-text-secondary">{r.skill_label ?? r.skill ?? "report"}</span>
                    {r.recommendation && <Tag variant={recVariant(r.recommendation)}>{r.recommendation}</Tag>}
                    {r.fair_value_low_eur != null && r.fair_value_high_eur != null && (
                      <span className="font-mono text-xs text-text-label">
                        FV €{r.fair_value_low_eur}–{r.fair_value_high_eur}
                        {r.upside_high_pct_eur != null && (
                          <span className={r.upside_high_pct_eur >= 0 ? "text-success" : "text-danger"}>
                            {" "}
                            ({r.upside_high_pct_eur >= 0 ? "+" : ""}
                            {r.upside_high_pct_eur}%)
                          </span>
                        )}
                      </span>
                    )}
                    {r.report_path && (
                      <button
                        type="button"
                        onClick={() => openInOs(r.report_path!)}
                        className="ml-auto text-xs text-accent hover:underline"
                      >
                        open .docx ↗
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </Panel>
  )
}

function HypothesisTracker() {
  const { data, isLoading } = useHypotheses()
  return (
    <Panel
      title="hypothesis tracker"
      meta={data ? `${data.count} open` : undefined}
      statusDotColor="accent"
    >
      {isLoading ? (
        <Skeleton className="h-24" />
      ) : !data?.hypotheses.length ? (
        <p className="text-sm text-text-label">
          no hypotheses in {data?.source ?? "Hypothesis_Tracker.md"} yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {data.hypotheses.map((h, i) => (
            <li key={i} className="whitespace-pre-wrap rounded-sm border border-border/60 px-2.5 py-1.5 text-sm text-text-secondary">
              <InlineMd text={h.text} />
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
