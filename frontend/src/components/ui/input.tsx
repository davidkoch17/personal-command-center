import * as React from "react"
import { cn } from "@/lib/utils"

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  /** Use monospace — for numeric / ticker / path inputs. */
  mono?: boolean
}

/**
 * Text input in the Cockpit style: panel background, 1px border, accent focus
 * border with no glow.
 */
export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, mono = false, type = "text", ...props }, ref) => {
    return (
      <input
        ref={ref}
        type={type}
        className={cn(
          "h-9 w-full rounded bg-bg-panel border border-border px-3 text-sm text-text placeholder:text-text-label",
          "transition-colors focus-visible:outline-none focus-visible:border-border-focus",
          "disabled:cursor-not-allowed disabled:text-text-disabled",
          mono && "font-mono",
          className,
        )}
        {...props}
      />
    )
  },
)
Input.displayName = "Input"
