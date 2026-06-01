import { cn } from "@/lib/utils"

export type StatusColor =
  | "accent"
  | "success"
  | "warning"
  | "danger"
  | "muted"

const COLOR_MAP: Record<StatusColor, string> = {
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  muted: "bg-text-label",
}

interface StatusDotProps {
  color?: StatusColor
  /** Render a hollow ring (pending / inactive) instead of a filled dot. */
  hollow?: boolean
  /** Subtle pulse, e.g. for live feeds or an active listening state. */
  pulse?: boolean
  className?: string
}

/**
 * Small semantic status circle. Filled by default; `hollow` draws the
 * pending/inactive ○ state. Status dots replace emojis throughout the UI.
 */
export function StatusDot({
  color = "muted",
  hollow = false,
  pulse = false,
  className,
}: StatusDotProps) {
  if (hollow) {
    const ringMap: Record<StatusColor, string> = {
      accent: "border-accent",
      success: "border-success",
      warning: "border-warning",
      danger: "border-danger",
      muted: "border-text-label",
    }
    return (
      <div
        className={cn(
          "w-2 h-2 rounded-full border bg-transparent",
          ringMap[color],
          pulse && "animate-pulse-dot",
          className,
        )}
      />
    )
  }
  return (
    <div
      className={cn(
        "w-2 h-2 rounded-full",
        COLOR_MAP[color],
        pulse && "animate-pulse-dot",
        className,
      )}
    />
  )
}
