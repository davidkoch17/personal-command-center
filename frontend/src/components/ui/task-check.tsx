import { cn } from "@/lib/utils"
import { InlineMd } from "@/components/ui/inline-markdown"

interface TaskCheckProps {
  checked: boolean
  onToggle: () => void
  children: React.ReactNode
  disabled?: boolean
  className?: string
}

/**
 * Toggleable task row using the Cockpit ○ / ● dot convention instead of a native
 * checkbox. Filled accent dot = done (with struck, dim label); hollow = open.
 */
export function TaskCheck({
  checked,
  onToggle,
  children,
  disabled = false,
  className,
}: TaskCheckProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      className={cn(
        "group flex w-full items-start gap-2.5 rounded-sm px-1.5 py-1 text-left text-sm transition-colors",
        "hover:bg-bg-panel-hover disabled:opacity-50 disabled:pointer-events-none",
        className,
      )}
    >
      <span
        className={cn(
          "mt-1 h-3 w-3 shrink-0 rounded-full border transition-colors",
          checked
            ? "bg-accent border-accent"
            : "border-text-label group-hover:border-text-secondary",
        )}
      />
      <span className={cn(checked ? "text-text-secondary line-through" : "text-text")}>
        {typeof children === "string" ? <InlineMd text={children} /> : children}
      </span>
    </button>
  )
}
