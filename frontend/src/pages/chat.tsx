import { useEffect } from "react"
import { ChatSession } from "@/components/chat/chat-session"

/**
 * The full-window chat — "talking to Claude Code directly" inside the command
 * center. Opened in its own browser window (see ``lib/chat-window.ts``); the
 * session surface itself lives in ``components/chat/chat-session.tsx`` and is
 * shared with the Home "Ask Claude" overlay.
 */
export function Chat() {
  const page = new URLSearchParams(window.location.search).get("page")

  // Go true (borderless) fullscreen. The browser blocks requestFullscreen
  // without a user gesture, so we arm it on the first click/keypress in the
  // window; the header toggle can exit/re-enter at will.
  useEffect(() => {
    const goFs = () => {
      const el = document.documentElement
      if (!document.fullscreenElement && el.requestFullscreen) {
        el.requestFullscreen().catch(() => {})
      }
      window.removeEventListener("pointerdown", goFs)
      window.removeEventListener("keydown", goFs)
    }
    window.addEventListener("pointerdown", goFs)
    window.addEventListener("keydown", goFs)
    return () => {
      window.removeEventListener("pointerdown", goFs)
      window.removeEventListener("keydown", goFs)
    }
  }, [])

  return <ChatSession page={page} />
}
