import { ArrowUpRight, Bot } from "lucide-react"
import type { ProjectCard as ProjectCardData } from "@/lib/types"
import { StatusDot } from "@/components/ui/status-dot"
import { projectStatusMeta } from "@/lib/status"
import { formatBoth } from "@/lib/dates"
import { cn } from "@/lib/utils"

interface ProjectCardProps {
  project: ProjectCardData
  className?: string
}

/**
 * Project summary card. The whole card is an anchor that opens the full-screen
 * workspace in a NEW TAB (Cockpit deep-dive pattern).
 */
export function ProjectCard({ project, className }: ProjectCardProps) {
  const { color, label } = projectStatusMeta(project.status)
  const deadline = project.big_milestone_date
    ? formatBoth(project.big_milestone_date)
    : null

  return (
    <a
      href={`/workspace/project/${project.id}`}
      target="_blank"
      rel="noopener noreferrer"
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

      <div className="space-y-2 text-sm">
        <div>
          <div className="label mb-0.5">milestone</div>
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
          <div className="label mb-0.5">next step</div>
          <span className="line-clamp-2 text-text-secondary">
            {project.next_step || "—"}
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
        {project.has_agents && (
          <span className="ml-auto flex items-center gap-1 font-mono text-[10px] uppercase text-accent">
            <Bot className="h-3 w-3" />
            agents
          </span>
        )}
      </div>
    </a>
  )
}
