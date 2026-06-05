import { useLocation } from "react-router-dom"
import { Sparkles } from "lucide-react"
import { openChatWindow } from "@/lib/chat-window"

/**
 * A clean pull-tab on the right edge of every page (mounted once in the
 * AppShell). Collapsed it's a small rounded icon tab; on hover it slides out to
 * reveal the label. Clicking opens the Claude chat in its own fullscreen browser
 * window — on a second monitor when one is connected (see ``lib/chat-window.ts``).
 */
export function JarvisDock() {
  const location = useLocation()
  return (
    <button
      type="button"
      onClick={() => void openChatWindow(location.pathname)}
      aria-label="open claude chat"
      title="open claude chat (new window)"
      className="no-print group fixed right-0 top-1/2 z-40 flex -translate-y-1/2 items-center overflow-hidden rounded-l-xl border border-r-0 border-border bg-bg-panel/95 shadow-lg backdrop-blur transition-colors hover:border-accent/50 hover:bg-bg-panel-hover"
    >
      <span className="flex h-11 w-11 items-center justify-center text-accent transition-transform group-hover:scale-110">
        <Sparkles className="h-[18px] w-[18px]" />
      </span>
      <span className="max-w-0 overflow-hidden whitespace-nowrap text-sm font-medium text-text transition-all duration-300 ease-out group-hover:max-w-[110px] group-hover:pr-4">
        ask claude
      </span>
    </button>
  )
}
