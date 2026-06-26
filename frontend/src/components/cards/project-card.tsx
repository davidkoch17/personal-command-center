import { ArrowUpRight, Bot, ListChecks } from "lucide-react"
import type { ProjectCard as ProjectCardData } from "@/lib/types"
import { StatusDot } from "@/components/ui/status-dot"
import { projectStatusMeta } from "@/lib/status"
import { formatBoth, formatRelative } from "@/lib/dates"
import { cn } from "@/lib/utils"

interface ProjectCardProps {
  project: ProjectCardData
  className?: string
  /** Where the card links. Defaults to the deep-dive workspace. */
  href?: string
  /** Open in a new tab (workspace pattern). Set false for in-app pages. */
  newTab?: boolean
}

/**
 * Project summary card (Projects pillar, spec § e). Shows phase · next milestone
 * · open project-tagged task count + top task · last activity. NO percent-complete
 * bar (David: makes no sense for these projects). The whole card is an anchor —
 * by default it opens the full-screen workspace in a NEW TAB (Cockpit deep-dive
 * pattern); the Personal Brand card points at the Brand site instead.
 */
export function ProjectCard({ project, className, href, newTab = true }: ProjectCardProps) {
  const { color, label } = projectStatusMeta(project.status)
  const deadline = project.big_milestone_date
    ? formatBoth(project.big_milestone_date)
    : null
  const target = href ?? `/workspace/project/${project.id}`
  const taskCount = project.open_task_count ?? 0

  return (
    <a
      href={target}
      {...(newTab ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      className={cn(
        "panel panel-hover group flex flex-col gap-3 transition-colors",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <StatusDot color={color} />
          <span className="font-mono text-xs text-text-secondary">
            {project.id}
          </span>
          <span className="truncate text-sm font-medium text-text">
            {project.name}
          </span>
        </div>
        <ArrowUpRight className="h-4 w-4 shrink-0 text-text-label group-hover:text-accent transition-colors" />
      </div>

      {project.phase && (
        <div>
          <div className="label mb-0.5">phase</div>
          <span className="line-clamp-1 text-sm text-text-secondary">{project.phase}</span>
        </div>
      )}

      <div className="space-y-2 text-sm">
        <div>
          <div className="label mb-0.5">next milestone</div>
          {project.big_milestone ? (
            <div className="flex items-baseline justify-between gap-2">
              <span className="truncate text-text">{project.big_milestone}</span>
              {deadline && (
                <span className="shrink-0 font-mono text-xs text-accent tabular-nums">
                  {deadline}
                </span>
              )}
            </div>
          ) : (
            <span className="text-text-label">—</span>
          )}
        </div>

        <div>
          <div className="label mb-0.5 flex items-center gap-1.5">
            <ListChecks className="h-3 w-3" />
            open tasks
            <span className="font-mono text-text-secondary">{taskCount}</span>
          </div>
          <span className="line-clamp-2 text-text-secondary">
            {project.top_task || (taskCount === 0 ? "no tagged tasks" : "—")}
          </span>
        </div>
      </div>

      <div className="mt-auto flex items-center gap-2 pt-1">
        <span className="label">{label}</span>
        {project.flow && (
          <span className="font-mono text-[10px] uppercase text-text-label">
            flow {project.flow.toLowerCase()}
          </span>
        )}
        {project.last_activity && (
          <span className="ml-auto font-mono text-[10px] text-text-label">
            {formatRelative(project.last_activity)}
          </span>
        )}
        {project.has_agents && (
          <span className="flex items-center gap-1 font-mono text-[10px] uppercase text-accent">
            <Bot className="h-3 w-3" />
            agents
          </span>
        )}
      </div>
    </a>
  )
}
