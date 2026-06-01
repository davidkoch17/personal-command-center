import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const tagVariants = cva(
  "inline-flex items-center gap-1.5 rounded-sm px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider",
  {
    variants: {
      variant: {
        muted: "bg-bg border border-border text-text-secondary",
        accent: "bg-accent-soft text-text border border-accent-dim/40",
        success: "bg-success/10 text-success border border-success/30",
        warning: "bg-warning/10 text-warning border border-warning/30",
        danger: "bg-danger/10 text-danger border border-danger/30",
      },
    },
    defaultVariants: {
      variant: "muted",
    },
  },
)

export interface TagProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof tagVariants> {}

/** Small status / category pill. Lowercase content recommended. */
export function Tag({ className, variant, ...props }: TagProps) {
  return (
    <span className={cn(tagVariants({ variant }), className)} {...props} />
  )
}
