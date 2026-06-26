import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { CountdownDisplay } from "@/components/ui/countdown-display"
import { ChecklistItem } from "@/components/ui/checklist-item"
import { MetricPanel } from "@/components/finance/metric-panel"
import {
  useCareerOverview,
  useCareerWorkspace,
  useCareerActivity,
  useCareerModel,
  useToggleChecklist,
} from "@/hooks/useCareer"
import { openInOs } from "@/lib/open-in-os"
import { formatBoth } from "@/lib/dates"
import { toast } from "@/lib/toast-store"

export function Career() {
  const overview = useCareerOverview()
  const ws = useCareerWorkspace()
  const activity = useCareerActivity()
  const model = useCareerModel()
  const toggle = useToggleChecklist()

  const preview = (ws.data?.onboarding ?? []).slice(0, 5)
  const modelReady = model.data?.status === "ready"

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
          dotColor={model.isLoading ? "muted" : modelReady ? "success" : "warning"}
          value={
            model.isLoading ? (
              <Skeleton className="h-7 w-24" />
            ) : modelReady ? (
              <button
                type="button"
                onClick={() => model.data?.path && openInOs(model.data.path)}
                className="text-left text-accent hover:underline"
                title={model.data?.path ?? undefined}
              >
                ready ↗
              </button>
            ) : (
              <span className="text-text-label">not started</span>
            )
          }
          caption={
            model.isLoading
              ? "checking 05_Current_Job…"
              : modelReady
                ? `${model.data?.name} · ${formatBoth(model.data!.last_modified!)}`
                : "build in cowork → save to 05_Current_Job"
          }
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
      <Panel title="recent activity" meta="3_Career · latest files" statusDotColor="accent">
        {activity.isLoading ? (
          <Skeleton className="h-24" />
        ) : (activity.data?.items.length ?? 0) === 0 ? (
          <p className="text-sm text-text-label">no recent files in 3_Career</p>
        ) : (
          <div className="space-y-1">
            {activity.data!.items.map((item) => (
              <button
                key={item.rel_path}
                type="button"
                onClick={() => openInOs(item.rel_path)}
                className="flex w-full items-baseline justify-between gap-3 rounded px-1 py-0.5 text-left hover:bg-bg-panel-hover"
                title={item.rel_path}
              >
                <span className="truncate text-sm text-text">{item.name}</span>
                <span className="shrink-0 font-mono text-xs text-text-label">
                  {item.folder} · {formatBoth(item.modified)}
                </span>
              </button>
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}
