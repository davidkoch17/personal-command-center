import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium transition-[colors,transform] active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus disabled:pointer-events-none disabled:scale-100 disabled:text-text-disabled disabled:border-border",
  {
    variants: {
      variant: {
        // Primary: accent background, bg-colored text
        primary: "bg-accent text-bg hover:bg-accent-dim",
        // Secondary: transparent, bordered
        secondary:
          "bg-transparent border border-border text-text hover:border-accent-dim hover:bg-bg-panel-hover",
        // Ghost: no border, subtle hover
        ghost: "bg-transparent text-text-secondary hover:bg-bg-panel-hover hover:text-text",
        // Danger: destructive actions
        danger: "bg-danger text-bg hover:opacity-90",
      },
      size: {
        sm: "h-7 px-2.5 text-xs rounded-sm",
        md: "h-9 px-3.5 text-sm rounded",
        lg: "h-10 px-5 text-sm rounded",
        icon: "h-9 w-9 rounded",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Render as the child element (e.g. an `<a>` or router `<Link>`). */
  asChild?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    )
  },
)
Button.displayName = "Button"

export { buttonVariants }
