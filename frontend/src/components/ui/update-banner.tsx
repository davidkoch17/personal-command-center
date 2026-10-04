import { useUpdateStore } from "@/lib/update-store"

/**
 * Chunk 9.8 — shown when a new deploy's service worker has already taken
 * control of this tab (main.tsx's controllerchange listener). The in-memory
 * page is now stale relative to what the next request would get served, so a
 * reload is the only way to actually pick up the new build. Deliberately
 * persistent (no auto-dismiss, unlike the regular Toaster) — the user should
 * be able to act on it whenever convenient, not lose it after 5 seconds.
 */
export function UpdateBanner() {
  const available = useUpdateStore((s) => s.available)
  if (!available) return null
  return (
    <div
      role="status"
      aria-live="polite"
      className="no-print fixed inset-x-0 bottom-0 z-[70] flex items-center justify-center gap-3 border-t border-accent/40 bg-bg-panel/95 px-4 py-2.5 backdrop-blur"
    >
      <span className="text-sm text-text">New version available</span>
      <button
        type="button"
        onClick={() => window.location.reload()}
        className="rounded-sm border border-accent px-2.5 py-1 font-mono text-xs text-accent transition-colors hover:bg-accent/10"
      >
        reload
      </button>
    </div>
  )
}
