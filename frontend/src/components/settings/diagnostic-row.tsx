import { StatusDot, type StatusColor } from "@/components/ui/status-dot"
import type { DiagnosticCheck } from "@/hooks/useDiagnostics"

const STATUS_META: Record<string, { color: StatusColor; label: string }> = {
  ok: { color: "success", label: "ok" },
  not_configured: { color: "muted", label: "not configured" },
  error: { color: "danger", label: "error" },
}

/** One integration health row: dot + name + status + detail. */
export function DiagnosticRow({ check }: { check: DiagnosticCheck }) {
  const meta = STATUS_META[check.status] ?? { color: "warning" as StatusColor, label: check.status }
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border py-2 last:border-0">
      <div className="flex items-center gap-2 min-w-0">
        <StatusDot color={meta.color} />
        <span className="text-sm text-text">{check.name}</span>
      </div>
      <div className="flex items-center gap-3 text-right">
        {check.detail && (
          <span className="truncate font-mono text-xs text-text-secondary">{check.detail}</span>
        )}
        <span className="label shrink-0">{meta.label}</span>
      </div>
    </div>
  )
}
