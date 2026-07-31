import { Inbox, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

interface EmptyStateProps {
  message: string
  icon?: LucideIcon
  className?: string
}

/** Muted icon + one-line hint. Replaces bare gray placeholder text everywhere
 *  a panel/card has no data yet. */
export function EmptyState({ message, icon: Icon = Inbox, className }: EmptyStateProps) {
  return (
    <div className={cn("flex items-center gap-2 py-1 text-sm text-text-label", className)}>
      <Icon className="h-4 w-4 shrink-0 text-text-disabled" />
      <span>{message}</span>
    </div>
  )
}
