import { useRef, useState } from "react"
import { ArrowRight, Mic } from "lucide-react"
import { ChatSession } from "@/components/chat/chat-session"
import { useJarvisBriefing } from "@/hooks/useJarvisBriefing"
import { cn } from "@/lib/utils"

const RECENT_KEY = "cc.askclaude.recent"
const RECENT_MAX = 8

function loadRecent(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY)
    const parsed = raw ? (JSON.parse(raw) as unknown) : []
    return Array.isArray(parsed) ? parsed.filter((q) => typeof q === "string") : []
  } catch {
    return []
  }
}

function saveRecent(question: string): string[] {
  const next = [question, ...loadRecent().filter((q) => q !== question)].slice(0, RECENT_MAX)
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next))
  } catch {
    /* storage full/blocked — recall is best-effort */
  }
  return next
}

/**
 * Ask Claude bar between NOW and STATE (Home_Redesign_Spec.md):
 * full-width text input + 🎙 voice (existing Jarvis pipeline). Submitting opens
 * the chat as a right-side overlay (full-width sheet on mobile) and auto-sends
 * the question. Recent questions persist in localStorage for quick recall.
 */
export function AskClaudeBar() {
  const [value, setValue] = useState("")
  const [focused, setFocused] = useState(false)
  const [recent, setRecent] = useState<string[]>(loadRecent)
  const [overlayQuestion, setOverlayQuestion] = useState<string | null>(null)
  // Re-keying the overlay per ask gives each question a fresh chat session.
  const askSeq = useRef(0)

  // Voice path: the mic IS the Jarvis pipeline (briefing → listen → route).
  const { state, subtitle, trigger } = useJarvisBriefing()

  function submit(question?: string) {
    const q = (question ?? value).trim()
    if (!q) return
    setRecent(saveRecent(q))
    askSeq.current += 1
    setOverlayQuestion(q)
    setValue("")
    setFocused(false)
  }

  const showRecent = focused && !value.trim() && recent.length > 0

  return (
    <>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onFocus={() => setFocused(true)}
              onBlur={() => window.setTimeout(() => setFocused(false), 150)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submit()
              }}
              placeholder="ask claude — type a question or click the mic to speak…"
              className="w-full rounded-lg border border-border bg-bg-panel px-4 py-3 text-sm text-text placeholder:text-text-label focus:border-accent focus:outline-none"
            />
            {showRecent && (
              <div className="absolute inset-x-0 top-full z-20 mt-1 rounded-lg border border-border bg-bg-panel p-1 shadow-lg">
                {recent.map((q) => (
                  <button
                    key={q}
                    type="button"
                    // onMouseDown so it fires before the input's blur hides the list.
                    onMouseDown={() => submit(q)}
                    className="block w-full truncate rounded-sm px-3 py-1.5 text-left text-xs text-text-secondary hover:bg-bg-panel-hover hover:text-text"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={trigger}
            aria-label={state === "idle" ? "speak to jarvis" : "cancel jarvis"}
            title={state === "idle" ? "speak to jarvis" : "cancel"}
            className={cn(
              "flex h-[46px] w-[46px] shrink-0 items-center justify-center rounded-lg border transition-colors",
              state === "idle"
                ? "border-border bg-bg-panel text-text-secondary hover:border-accent-dim hover:text-text"
                : "border-accent bg-accent-soft/30 text-accent",
              state === "listening" && "animate-pulse",
            )}
          >
            <Mic className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => submit()}
            disabled={!value.trim()}
            aria-label="ask claude"
            className="flex h-[46px] w-[46px] shrink-0 items-center justify-center rounded-lg bg-accent text-white transition-colors hover:bg-accent-dim disabled:opacity-40"
          >
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
        {/* Jarvis live caption (speaking/listening/heard …) */}
        {subtitle && (
          <p className="animate-fade-in px-1 font-mono text-xs text-text-secondary">{subtitle}</p>
        )}
      </div>

      {overlayQuestion !== null && (
        <ChatOverlay key={askSeq.current} question={overlayQuestion} onClose={() => setOverlayQuestion(null)} />
      )}
    </>
  )
}

/** Right-side chat overlay (modal-width sheet on mobile). */
function ChatOverlay({ question, onClose }: { question: string; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50">
      {/* Backdrop — click to dismiss. */}
      <button
        type="button"
        aria-label="close chat"
        onClick={onClose}
        className="absolute inset-0 bg-black/40"
      />
      <div className="absolute inset-y-0 right-0 w-full max-w-full border-l border-border bg-bg shadow-2xl sm:max-w-[560px]">
        <ChatSession embedded page="home" initialMessage={question} onClose={onClose} />
      </div>
    </div>
  )
}
