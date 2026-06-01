import { useEffect, useRef, useState, type MutableRefObject } from "react"
import { useNavigate } from "react-router-dom"
import { cn } from "@/lib/utils"
import { api, API_BASE } from "@/lib/api"
import { toast } from "@/lib/toast-store"

type VoiceState = "idle" | "listening" | "processing" | "speaking"

interface RouteResponse {
  action: "navigate" | "run_skill" | "capture_inbox" | "answer" | "unclear"
  navigate_to?: string
  skill_name?: string
  skill_args?: Record<string, unknown>
  capture_text?: string
  answer_text?: string
  spoken_response?: string
}

const STATE_LABEL: Record<VoiceState, string> = {
  idle: "push to talk",
  listening: "listening…",
  processing: "thinking…",
  speaking: "speaking…",
}

const STATE_DOT: Record<VoiceState, string> = {
  idle: "bg-text-label",
  listening: "bg-accent animate-pulse-dot",
  processing: "bg-warning animate-pulse-dot",
  speaking: "bg-success animate-pulse-dot",
}

/**
 * Persistent push-to-talk bar, pinned bottom-center (Jarvis voice layer).
 *
 * Hold the button → browser records mic audio → on release it is transcribed
 * by local Whisper (`/api/voice/transcribe`), routed to an action by Claude
 * (`/api/voice/route`), the action is executed in-app, and Piper speaks the
 * acknowledgement (`/api/voice/speak`). A live waveform reflects the mic level
 * while listening and a calm shimmer otherwise.
 */
export function VoiceBar() {
  const navigate = useNavigate()
  const [state, setState] = useState<VoiceState>("idle")
  const [transcript, setTranscript] = useState("")

  const mediaRecorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)

  function teardownAudio() {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    audioCtxRef.current?.close().catch(() => {})
    audioCtxRef.current = null
    analyserRef.current = null
  }

  // Stop any media on unmount.
  useEffect(() => () => teardownAudio(), [])

  async function startRecording() {
    if (state !== "idle") return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      setState("listening")

      // Wire an analyser for the live waveform.
      const ctx = new AudioContext()
      const source = ctx.createMediaStreamSource(stream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 64
      source.connect(analyser)
      audioCtxRef.current = ctx
      analyserRef.current = analyser

      mediaRecorder.current = new MediaRecorder(stream)
      chunks.current = []
      mediaRecorder.current.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data)
      }
      mediaRecorder.current.start()
    } catch (err) {
      teardownAudio()
      setState("idle")
      toast.error("microphone unavailable", String(err))
    }
  }

  function stopRecording() {
    const recorder = mediaRecorder.current
    if (!recorder || state !== "listening") return
    setState("processing")
    recorder.onstop = handleRecorded
    recorder.stop()
  }

  async function handleRecorded() {
    // Free the mic + analyser as soon as the clip is captured.
    teardownAudio()

    try {
      const blob = new Blob(chunks.current, { type: "audio/webm" })
      const formData = new FormData()
      formData.append("audio", blob, "recording.webm")

      // 1. Transcribe (multipart — bypass the JSON api helper).
      const transcribeRes = await fetch(`${API_BASE}/api/voice/transcribe`, {
        method: "POST",
        body: formData,
      })
      if (!transcribeRes.ok) throw new Error(await transcribeRes.text())
      const { text } = (await transcribeRes.json()) as { text: string }
      setTranscript(text)

      // 2. Route the intent through Claude.
      const route = await api.post<RouteResponse>("/api/voice/route", {
        text,
        current_page: window.location.pathname,
      })

      // 3. Execute the chosen action.
      await executeAction(route)

      // 4. Speak the acknowledgement, then return to idle.
      const spoken = route.spoken_response || route.answer_text
      if (spoken) {
        await speak(spoken)
      }
    } catch (err) {
      toast.error("voice command failed", String(err))
    } finally {
      setState("idle")
    }
  }

  async function executeAction(route: RouteResponse) {
    switch (route.action) {
      case "navigate":
        if (route.navigate_to) navigate(route.navigate_to)
        break
      case "run_skill":
        if (route.skill_name) {
          await api.post(`/api/skills/${route.skill_name}/run`, {
            args: route.skill_args ?? {},
            label: route.skill_name,
          })
          toast.success(`running ${route.skill_name}`, "track it on background runs")
        }
        break
      case "capture_inbox":
        if (route.capture_text) {
          await api.post("/api/inbox/capture", {
            content: route.capture_text,
            source: "voice",
          })
          toast.success("captured to inbox")
        }
        break
      // "answer" and "unclear" are spoken-only — nothing further to do.
      default:
        break
    }
  }

  async function speak(text: string) {
    setState("speaking")
    const res = await fetch(`${API_BASE}/api/voice/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    })
    if (!res.ok) return // speech is best-effort; the action already ran
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
  }

  return (
    <div className="no-print fixed bottom-4 left-1/2 z-50 -translate-x-1/2 px-2">
      <div
        className={cn(
          "panel flex items-center gap-3 bg-bg-panel/95 px-4 py-2 backdrop-blur",
          "transition-opacity duration-300",
          state === "idle" ? "opacity-90 hover:opacity-100" : "opacity-100",
        )}
      >
        <button
          type="button"
          aria-label={STATE_LABEL[state]}
          className="flex items-center gap-3 outline-none"
          onMouseDown={startRecording}
          onMouseUp={stopRecording}
          onMouseLeave={() => state === "listening" && stopRecording()}
          onTouchStart={(e) => {
            e.preventDefault()
            startRecording()
          }}
          onTouchEnd={(e) => {
            e.preventDefault()
            stopRecording()
          }}
        >
          <div className={cn("h-2 w-2 rounded-full transition-colors", STATE_DOT[state])} />
          <span className="label">{STATE_LABEL[state]}</span>
          <LiveWaveform state={state} analyserRef={analyserRef} />
        </button>
        {transcript && (
          <span className="hidden max-w-[16rem] truncate text-xs italic text-text-secondary sm:inline">
            “{transcript}”
          </span>
        )}
      </div>
    </div>
  )
}

const BAR_COUNT = 12

/**
 * Canvas waveform. While `listening` it reflects the live mic level from the
 * AnalyserNode; otherwise it shows a subtle monochrome shimmer. Kept small and
 * desaturated so it reads as ambient, not a focal point.
 */
function LiveWaveform({
  state,
  analyserRef,
}: {
  state: VoiceState
  analyserRef: MutableRefObject<AnalyserNode | null>
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const w = canvas.clientWidth
    const h = canvas.clientHeight
    canvas.width = w * dpr
    canvas.height = h * dpr
    ctx.scale(dpr, dpr)

    let raf = 0
    const freq = new Uint8Array(BAR_COUNT)

    // Cockpit theme tokens (see tailwind.config.ts) — kept in sync by hand
    // because the palette is defined as static hex, not CSS variables.
    const accent = "#2563EB" // accent
    const label = "#5C6470" // text-label

    const draw = () => {
      ctx.clearRect(0, 0, w, h)
      const analyser = analyserRef.current
      const active = state === "listening" && analyser
      ctx.fillStyle = state === "idle" ? label : accent

      let levels: number[]
      if (active) {
        analyser!.getByteFrequencyData(freq)
        levels = Array.from(freq.slice(0, BAR_COUNT), (v) => v / 255)
      } else {
        // Calm shimmer for idle/processing/speaking.
        const t = performance.now() / 320
        const amp = state === "idle" ? 0.18 : 0.5
        levels = Array.from({ length: BAR_COUNT }, (_, i) =>
          (0.35 + 0.65 * Math.abs(Math.sin(t + i * 0.6))) * amp,
        )
      }

      const gap = 2
      const barW = (w - gap * (BAR_COUNT - 1)) / BAR_COUNT
      levels.forEach((lvl, i) => {
        const barH = Math.max(2, lvl * h)
        const x = i * (barW + gap)
        const y = (h - barH) / 2
        ctx.beginPath()
        ctx.roundRect(x, y, barW, barH, barW / 2)
        ctx.fill()
      })

      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => cancelAnimationFrame(raf)
  }, [state, analyserRef])

  return <canvas ref={canvasRef} className="h-4 w-16" aria-hidden />
}
