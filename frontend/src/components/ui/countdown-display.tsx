import { daysUntil } from "@/lib/status"
import { cn } from "@/lib/utils"

interface CountdownDisplayProps {
  /** Target ISO date (YYYY-MM-DD). */
  date: string
  label?: string
  className?: string
}

/** Huge monospace day-countdown to a target date. */
export function CountdownDisplay({ date, label, className }: CountdownDisplayProps) {
  const days = daysUntil(date)
  const past = days != null && days < 0

  return (
    <div className={cn("flex items-baseline gap-3", className)}>
      <span className="font-mono text-6xl font-medium tabular-nums text-accent leading-none">
        {days == null ? "—" : Math.abs(days)}
      </span>
      <div className="flex flex-col">
        <span className="font-mono text-sm text-text-secondary">
          {past ? "days since" : "days until"}
        </span>
        {label && <span className="text-sm text-text">{label}</span>}
        <span className="font-mono text-xs text-text-label">{date}</span>
      </div>
    </div>
  )
}
