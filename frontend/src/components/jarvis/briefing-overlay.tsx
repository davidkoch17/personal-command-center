import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { JarvisBall, type JarvisState } from "./jarvis-ball"
import { api, API_BASE } from "@/lib/api"

type Phase = "loading" | "speaking" | "listening" | "routing" | "done"

interface BriefingState {
  phase: Phase
  text: string
  suggestions: string[]
  transcript?: string
}

interface BriefingResponse {
  text: string
  suggestions: string[]
  spoken: string
}

interface RouteResponse {
  action: string
  navigate_to?: string
  spoken_response?: string
}

const PHASE_LABEL: Record<Phase, string> = {
  loading: "assembling briefing",
  speaking: "morning briefing",
  listening: "listening…",
  routing: "thinking…",
  done: "morning briefing",
}

function ballState(phase: Phase): JarvisState {
  if (phase === "listening") return "listening"
  if (phase === "speaking") return "speaking"
  if (phase === "routing") return "processing"
  return "idle"
}

/**
 * Full-screen briefing experience. On open it fetches a personalised briefing,
 * speaks it via Piper, then listens for David's pick and navigates. Voice steps
 * (speak/listen) degrade gracefully: if Piper/Whisper aren't installed the text
 * + clickable suggestions still work.
 */
export function BriefingOverlay({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const [state, setState] = useState<BriefingState>({
    phase: "loading",
    text: "",
    suggestions: [],
  })
  // Latest suggestions, read inside async callbacks without stale-closure risk.
  const suggestionsRef = useRef<string[]>([])
  const startedRef = useRef(false)

  useEffect(() => {
    // Guard against React 18 StrictMode double-invoke.
    if (startedRef.current) return
    startedRef.current = true
    void startBriefing()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Esc closes the overlay.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  async function startBriefing() {
    try {
      const briefing = await api.post<BriefingResponse>("/api/voice/briefing", {})
      suggestionsRef.current = briefing.suggestions ?? []
      setState({
        phase: "speaking",
        text: briefing.text,
        suggestions: briefing.suggestions ?? [],
      })

      // Speak it (best-effort). If Piper isn't installed, skip straight to listening.
      const spoke = await playSpeech(briefing.spoken)
      if (spoke) {
        await listenForChoice()
      } else {
        // No audio — let David pick a suggestion by click/voice manually.
        setState((s) => ({ ...s, phase: "done" }))
      }
    } catch {
      setState((s) => ({
        ...s,
        phase: "done",
        text: s.text || "Good morning, David.",
      }))
    }
  }

  /** Play TTS for `text`. Returns true if audio actually played. */
  async function playSpeech(text: string): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/api/voice/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      })
      if (!res.ok) return false
      const url = URL.createObjectURL(await res.blob())
      await new Promise<void>((resolve) => {
        const audio = new Audio(url)
        audio.onended = () => {
          URL.revokeObjectURL(url)
          resolve()
        }
        audio.onerror = () => {
          URL.revokeObjectURL(url)
          resolve()
        }
        void audio.play().catch(() => resolve())
      })
      return true
    } catch {
      return false
    }
  }

  async function listenForChoice() {
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setState((s) => ({ ...s, phase: "done" }))
      return
    }
    setState((s) => ({ ...s, phase: "listening" }))

    const recorder = new MediaRecorder(stream)
    const chunks: Blob[] = []
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data)
    }
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      try {
        const blob = new Blob(chunks, { type: "audio/webm" })
        const formData = new FormData()
        formData.append("audio", blob, "rec.webm")
        const transcribeRes = await fetch(`${API_BASE}/api/voice/transcribe`, {
          method: "POST",
          body: formData,
        })
        if (!transcribeRes.ok) throw new Error(await transcribeRes.text())
        const { text } = (await transcribeRes.json()) as { text: string }
        setState((s) => ({ ...s, transcript: text, phase: "routing" }))
        await routeChoice(text)
      } catch {
        setState((s) => ({ ...s, phase: "done" }))
      }
    }
    recorder.start()
    setTimeout(() => recorder.state !== "inactive" && recorder.stop(), 5000)
  }

  /** Route a chosen command (from voice or a clicked suggestion). */
  async function routeChoice(text: string) {
    setState((s) => ({ ...s, phase: "routing", transcript: text }))
    try {
      const route = await api.post<RouteResponse>("/api/voice/route", {
        text,
        current_page: "/",
        context: { briefing_suggestions: suggestionsRef.current },
      })
      if (route.action === "navigate" && route.navigate_to) {
        navigate(route.navigate_to)
        onClose()
        return
      }
      await playSpeech(route.spoken_response || "Got it.")
      onClose()
    } catch {
      setState((s) => ({ ...s, phase: "done" }))
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-bg/95 backdrop-blur-md">
      <button
        onClick={onClose}
        className="absolute right-6 top-6 font-mono text-sm text-text-secondary hover:text-text"
      >
        esc · close
      </button>

      <JarvisBall size="large" state={ballState(state.phase)} />

      <div className="mt-12 max-w-2xl space-y-4 px-6 text-center">
        <p className="font-mono text-sm uppercase tracking-wider text-text-secondary">
          {PHASE_LABEL[state.phase]}
        </p>
        {state.text && (
          <p className="whitespace-pre-line text-lg leading-relaxed">{state.text}</p>
        )}
        {state.suggestions.length > 0 && (
          <ul className="space-y-2">
            {state.suggestions.map((s, i) => (
              <li key={i}>
                <button
                  type="button"
                  onClick={() => routeChoice(s)}
                  className="text-text-secondary transition-colors hover:text-accent"
                >
                  {i + 1}. {s}
                </button>
              </li>
            ))}
          </ul>
        )}
        {state.transcript && <p className="italic text-accent">“{state.transcript}”</p>}
      </div>
    </div>
  )
}
