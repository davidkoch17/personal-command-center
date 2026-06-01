import { useEffect } from "react"
import { cn } from "@/lib/utils"
import { useToastStore, type Toast } from "@/lib/toast-store"
import { StatusDot, type StatusColor } from "./status-dot"

const TONE_DOT: Record<Toast["tone"], StatusColor> = {
  default: "accent",
  success: "success",
  danger: "danger",
}

/**
 * Bottom-right toast stack. Auto-dismisses each toast after 5s. Mounted once in
 * the AppShell. Fire toasts via the `toast` helper in `lib/toast-store`.
 */
export function Toaster() {
  const toasts = useToastStore((s) => s.toasts)
  return (
    <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)]">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  )
}

function ToastItem({ toast }: { toast: Toast }) {
  const dismiss = useToastStore((s) => s.dismiss)
  useEffect(() => {
    const handle = window.setTimeout(() => dismiss(toast.id), 5000)
    return () => window.clearTimeout(handle)
  }, [toast.id, dismiss])

  return (
    <button
      type="button"
      onClick={() => dismiss(toast.id)}
      className={cn(
        "panel flex items-start gap-2.5 px-3 py-2.5 text-left bg-bg-panel/95 backdrop-blur",
        "transition-colors hover:bg-bg-panel-hover",
      )}
    >
      <div className="mt-1">
        <StatusDot color={TONE_DOT[toast.tone]} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-text">{toast.message}</p>
        {toast.detail && (
          <p className="mt-0.5 font-mono text-xs text-text-secondary break-all">
            {toast.detail}
          </p>
        )}
      </div>
    </button>
  )
}
