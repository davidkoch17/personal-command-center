import { cn } from "@/lib/utils"

interface ChecklistItemProps {
  checked: boolean
  onToggle: () => void
  children: React.ReactNode
  disabled?: boolean
}

/**
 * Toggleable checklist row (Cockpit ○ / ● convention). Bind `onToggle` to an API
 * mutation; the parent invalidates on success.
 */
export function ChecklistItem({
  checked,
  onToggle,
  children,
  disabled = false,
}: ChecklistItemProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      className={cn(
        "group flex w-full items-start gap-2.5 rounded-sm px-1.5 py-1 text-left text-sm transition-colors",
        "hover:bg-bg-panel-hover disabled:opacity-50 disabled:pointer-events-none",
      )}
    >
      <span
        className={cn(
          "mt-0.5 h-3 w-3 shrink-0 rounded-full border transition-colors",
          checked ? "bg-success border-success" : "border-text-label group-hover:border-text-secondary",
        )}
      />
      <span className={cn(checked ? "text-text-secondary line-through" : "text-text")}>
        {children}
      </span>
    </button>
  )
}
