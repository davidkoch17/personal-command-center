import * as React from "react"
import { cn } from "@/lib/utils"

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>

/** Multi-line text input in the Cockpit style (panel bg, accent focus border). */
export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(
          "w-full rounded bg-bg-panel border border-border px-3 py-2 text-sm text-text placeholder:text-text-label",
          "transition-colors focus-visible:outline-none focus-visible:border-border-focus",
          "disabled:cursor-not-allowed disabled:text-text-disabled resize-y min-h-[80px]",
          className,
        )}
        {...props}
      />
    )
  },
)
Textarea.displayName = "Textarea"
