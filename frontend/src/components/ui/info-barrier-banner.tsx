import { ShieldAlert } from "lucide-react"
import { useInfoBarrierActive } from "@/hooks/useSystem"
import { cn } from "@/lib/utils"

interface InfoBarrierBannerProps {
  /** Context-specific message, e.g. "restricted-sector name involved". */
  message?: string
  className?: string
}

/**
 * Warning banner shown only when the backend reports the info barrier active
 * (post Evercore start, or forced on in Settings). Renders nothing otherwise.
 */
export function InfoBarrierBanner({ message, className }: InfoBarrierBannerProps) {
  const active = useInfoBarrierActive()
  if (!active) return null
  return (
    <div
      className={cn(
        "flex items-center gap-2.5 rounded border border-warning/40 bg-warning/10 px-3 py-2",
        className,
      )}
    >
      <ShieldAlert className="h-4 w-4 shrink-0 text-warning" />
      <span className="text-sm text-text">
        info barrier active{message ? ` — ${message}` : ""}
      </span>
    </div>
  )
}
