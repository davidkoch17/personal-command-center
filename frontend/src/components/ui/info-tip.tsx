import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

/**
 * Small "ⓘ" affordance that reveals an explanation on hover/focus. Requires a
 * `TooltipProvider` somewhere above it (mounted app-wide in `App.tsx`). Phase
 * 15e, Section 5 — every metric gets a plain-language definition.
 */
export function InfoTip({ text, className }: { text: string; className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label="explain this metric"
          onClick={(e) => e.preventDefault()}
          className={cn(
            "inline-flex h-3.5 w-3.5 items-center justify-center rounded-full border border-border",
            "font-mono text-[9px] leading-none text-text-label",
            "hover:border-accent-dim hover:text-text focus:outline-none focus-visible:ring-1 focus-visible:ring-accent",
            className,
          )}
        >
          i
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-[260px] leading-relaxed">{text}</TooltipContent>
    </Tooltip>
  )
}
