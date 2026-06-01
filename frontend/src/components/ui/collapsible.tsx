import { useState, type ReactNode } from "react"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

interface CollapsibleProps {
  title: ReactNode
  /** Right-aligned metadata (monospace), e.g. a count or date. */
  meta?: ReactNode
  defaultOpen?: boolean
  children: ReactNode
  className?: string
}

/** Lightweight disclosure section. Header toggles visibility of its children. */
export function Collapsible({
  title,
  meta,
  defaultOpen = false,
  children,
  className,
}: CollapsibleProps) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className={cn("panel", className)}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 text-left"
      >
        <span className="flex items-center gap-2">
          <ChevronRight
            className={cn(
              "h-4 w-4 text-text-secondary transition-transform",
              open && "rotate-90",
            )}
          />
          <span className="label">{title}</span>
        </span>
        {meta && (
          <span className="font-mono text-xs text-text-secondary">{meta}</span>
        )}
      </button>
      {open && <div className="mt-3">{children}</div>}
    </div>
  )
}
