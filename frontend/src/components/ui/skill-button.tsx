import { useState, type ReactNode } from "react"
import { Button, type ButtonProps } from "@/components/ui/button"
import { toast } from "@/lib/toast-store"

interface SkillButtonProps extends Omit<ButtonProps, "onClick"> {
  /** Triggers the skill; resolve with the run_id for the toast. */
  onRun: () => Promise<{ run_id?: string } | void>
  children: ReactNode
}

/**
 * Generic background-skill trigger. Fires `onRun`, then toasts
 * "started in background — see background runs" with the run id (or an error).
 * Disabled while in flight.
 */
export function SkillButton({
  onRun,
  children,
  variant = "secondary",
  size = "sm",
  disabled,
  ...rest
}: SkillButtonProps) {
  const [pending, setPending] = useState(false)

  async function go() {
    setPending(true)
    try {
      const r = await onRun()
      toast.success("started in background — see background runs", r?.run_id)
    } catch (e) {
      toast.error("failed to start", String(e))
    } finally {
      setPending(false)
    }
  }

  return (
    <Button
      variant={variant}
      size={size}
      disabled={disabled || pending}
      onClick={go}
      {...rest}
    >
      {children}
    </Button>
  )
}
