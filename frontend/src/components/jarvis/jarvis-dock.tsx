import { useLocation } from "react-router-dom"
import { MessageSquare } from "lucide-react"
import { openChatWindow } from "@/lib/chat-window"

/**
 * A thin pull-tab docked to the right edge of every page (mounted once in the
 * AppShell). Clicking it opens the Claude chat in its own browser window —
 * placed on a second monitor when one is connected (see ``lib/chat-window.ts``).
 * It echoes the Jarvis ball's navy orb so it reads as the same assistant, but
 * uses a light CSS orb (no second WebGL canvas) since it's always mounted.
 */
export function JarvisDock() {
  const location = useLocation()
  return (
    <button
      type="button"
      onClick={() => void openChatWindow(location.pathname)}
      aria-label="open claude chat"
      title="open claude chat (new window)"
      className="no-print group fixed right-0 top-1/2 z-40 flex -translate-y-1/2 flex-col items-center gap-2 rounded-l-lg border border-r-0 border-border bg-bg-panel/90 px-2 py-3 shadow-lg backdrop-blur transition-all hover:bg-bg-panel-hover"
    >
      <span className="relative flex h-7 w-7 items-center justify-center">
        <span className="absolute inset-0 rounded-full bg-accent/30 animate-pulse" />
        <span className="absolute inset-0 rounded-full bg-gradient-to-br from-accent to-accent-soft opacity-90 transition-transform group-hover:scale-110" />
        <MessageSquare className="relative h-3.5 w-3.5 text-white" />
      </span>
      <span className="font-mono text-[10px] uppercase tracking-wider text-text-secondary [writing-mode:vertical-rl]">
        ask claude
      </span>
    </button>
  )
}
