import { cn } from "@/lib/utils"

interface StageStripProps {
  complete: number
  total: number
  className?: string
}

/**
 * Horizontal strip of `total` dots, the first `complete` filled in accent.
 * Used for idea validation progress (12 stages).
 */
export function StageStrip({ complete, total, className }: StageStripProps) {
  return (
    <div className={cn("flex items-center gap-1", className)}>
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          className={cn(
            "h-2 flex-1 rounded-full",
            i < complete ? "bg-accent" : "bg-border",
          )}
        />
      ))}
    </div>
  )
}
