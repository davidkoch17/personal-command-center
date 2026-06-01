import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { CountdownDisplay } from "@/components/ui/countdown-display"
import { ChecklistItem } from "@/components/ui/checklist-item"
import { MetricPanel } from "@/components/finance/metric-panel"
import {
  useCareerOverview,
  useCareerWorkspace,
  useToggleChecklist,
} from "@/hooks/useCareer"
import { toast } from "@/lib/toast-store"

export function Career() {
  const overview = useCareerOverview()
  const ws = useCareerWorkspace()
  const toggle = useToggleChecklist()

  const preview = (ws.data?.onboarding ?? []).slice(0, 5)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">career</h1>
        <Button asChild variant="secondary" size="sm">
          <a href="/workspace/career" target="_blank" rel="noopener noreferrer">
            open workspace ↗
          </a>
        </Button>
      </div>

      {/* Countdown */}
      <Panel title="evercore countdown" statusDotColor="accent">
        {overview.isLoading ? (
          <Skeleton className="h-16" />
        ) : (
          <CountdownDisplay
            date={overview.data?.start_date ?? "2026-07-01"}
            label="evercore start"
          />
        )}
      </Panel>

      {/* Status row */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricPanel
          label="3-statement model"
          dotColor="muted"
          value={<span className="text-text-label">—</span>}
          caption="status source pending"
        />
        <MetricPanel
          label="technicals"
          dotColor="accent"
          value={
            overview.isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              <span className="font-mono">
                {overview.data?.technicals_done ?? 0}/{overview.data?.technicals_total ?? 0}
              </span>
            )
          }
          caption="modules refreshed"
        />
        <MetricPanel
          label="admin"
          dotColor="success"
          value={
            overview.isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              <span className="font-mono">
                {overview.data?.onboarding_done ?? 0}/{overview.data?.onboarding_total ?? 0}
              </span>
            )
          }
          caption="onboarding items"
        />
        <MetricPanel
          label="first 90 days"
          dotColor="muted"
          value={<span className="text-text-label">—</span>}
          caption="plan source pending"
        />
      </div>

      {/* Prep checklist preview */}
      <Panel title="prep checklist" meta="onboarding · first 5" statusDotColor="accent">
        {ws.isLoading ? (
          <Skeleton className="h-24" />
        ) : preview.length === 0 ? (
          <p className="text-sm text-text-label">no onboarding items in vault</p>
        ) : (
          <div className="space-y-0.5">
            {preview.map((item, i) => (
              <ChecklistItem
                key={i}
                checked={item.checked}
                disabled={toggle.isPending}
                onToggle={() =>
                  toggle.mutate(
                    { checklist: "onboarding", index: i },
                    { onError: (e) => toast.error("could not toggle", String(e)) },
                  )
                }
              >
                {item.text}
              </ChecklistItem>
            ))}
          </div>
        )}
      </Panel>

      {/* Recent activity */}
      <Panel title="recent activity" statusDotColor="muted">
        <p className="text-sm text-text-label">
          recent-files-in-3_Career endpoint pending (backend phase)
        </p>
      </Panel>
    </div>
  )
}
